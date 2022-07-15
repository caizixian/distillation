#!/usr/bin/env python3
# Copyright 2022 Google
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import signal
from threading import Event
import bcc
from bcc import BPF
import enum
import multiprocessing
import sys
from pathlib import Path
import ctypes


class EventType(enum.Enum):
    EXIT = 1


TASK_COMM_LEN = 16

bpf_text = """
#include <linux/sched/signal.h>
#include <linux/sched.h>

// We use kernel terminology throughout
// Kernel process vs userspace thread
// Kernel thread group vs userspace process

enum event_type {
    PROCESS_EXIT
};

struct cycles_t {
    u64 cycles[NUM_CPUS];
};


struct data_t {
    u32 pid;
    char comm[TASK_COMM_LEN];
    enum event_type tag;
    u64 total_cycles;
    u64 gc_cycles;
};
BPF_PERF_OUTPUT(events);

BPF_HASH(process_in_gc, u32, bool, 8192);
BPF_PERF_ARRAY(cycle_events, NUM_CPUS);

BPF_ARRAY(system_cycles_start, u64, NUM_CPUS);
BPF_ARRAY(gc_cycles_start, u64, NUM_CPUS);

BPF_HASH(thread_group_cycles_total, u32, u64, 8192);
BPF_HASH(gc_cycles_total, u32, u64, 8192);

static bool get_in_gc(u32 pid) {
    bool *val;
    val = process_in_gc.lookup(&pid);
    if (!val) {
        return false;
    }
    return *val;
}

static void set_in_gc(u32 pid, bool val) {
    if (val) {
        process_in_gc.update(&pid, &val);
    } else {
        process_in_gc.delete(&pid);
    }
}

static void add_gc_cycles(u32 tgid, u32 cpu, u64 cnt) {
    u64* cnt_prev = gc_cycles_start.lookup(&cpu);
    if (cnt_prev) {
        u64 diff = cnt - *cnt_prev;
        gc_cycles_total.increment(tgid, diff);
    }
}

static void add_thread_group_cycles(u32 tgid, u32 cpu, u64 cnt) {
    u64* cnt_prev = system_cycles_start.lookup(&cpu);
    if (cnt_prev) {
        u64 diff = cnt - *cnt_prev;
        thread_group_cycles_total.increment(tgid, diff);
    }
}

int gc_run(struct pt_regs *ctx) {
    u32 cpu = bpf_get_smp_processor_id();
    u64 pid_tgid = bpf_get_current_pid_tgid();
    u32 pid = pid_tgid;
    u32 tgid = pid_tgid >> 32;
    set_in_gc(pid, true);
    u64 cnt = cycle_events.perf_read(cpu);
    gc_cycles_start.update(&cpu, &cnt);
    return 0;
}

int gc_run_ret(struct pt_regs *ctx) {
    u32 cpu = bpf_get_smp_processor_id();
    u64 pid_tgid = bpf_get_current_pid_tgid();
    u32 pid = pid_tgid;
    u32 tgid = pid_tgid >> 32;
    set_in_gc(pid, false);
    u64 cnt = cycle_events.perf_read(cpu);
    add_gc_cycles(tgid, cpu, cnt);
    return 0;
}

RAW_TRACEPOINT_PROBE(sched_switch) {
    //TP_PROTO(bool preempt,
    //         struct task_struct *prev,
    //         struct task_struct *next,
    //         unsigned int prev_state),
    struct task_struct *prev = (struct task_struct *)ctx->args[1];
    struct task_struct *next = (struct task_struct *)ctx->args[2];
    u32 pid = next->pid;
    u32 cpu = bpf_get_smp_processor_id();
    u64 cnt = cycle_events.perf_read(cpu);
    u32 prev_pid = prev->pid;
    u32 prev_tgid = prev->tgid;
    if (prev_pid != 0) {
        // from the previous switch until now, we weren't idling
        // we attribute the delta to the previous tgid/pid
        add_thread_group_cycles(prev_tgid, cpu, cnt);
        if (get_in_gc(prev_pid)) {
            add_gc_cycles(prev_tgid, cpu, cnt);
        }
    }
    if (pid != 0) {
        // we are not going into idle, so we need to set the initial values
        system_cycles_start.update(&cpu, &cnt);
        if (get_in_gc(pid)) {
            gc_cycles_start.update(&cpu, &cnt);
        }
    }
    return 0;
}

RAW_TRACEPOINT_PROBE(sched_process_free) {
    // TP_PROTO(struct task_struct *p)
    struct task_struct *p = (struct task_struct *)ctx->args[0];
    bool is_leader = (p->group_leader) == p;
    if (!is_leader) {
        return 0;
    }
    struct data_t data = {};
    u32 tgid = p->tgid;
    data.pid = tgid;
    bpf_probe_read_kernel_str(&data.comm, sizeof(data.comm), p->comm);
    u64* c;
    c = thread_group_cycles_total.lookup(&tgid);
    if (c) {
        data.total_cycles = *c;
        thread_group_cycles_total.delete(&tgid);
    } else {
        data.total_cycles = -1;
    }
    c = gc_cycles_total.lookup(&tgid);
    if (c) {
        data.gc_cycles = *c;
        gc_cycles_total.delete(&tgid);
    } else {
        data.gc_cycles = 0;
    }
    events.perf_submit(ctx, &data, sizeof(data));
    return 0;
}
"""


def render_tgid(pid: int) -> str:
    # NB Chrome is doing weird things to cmdline
    # https://unix.stackexchange.com/questions/432419/unexpected-non-null-encoding-of-proc-pid-cmdline
    p = Path("/proc") / str(pid) / "cmdline"
    if p.exists():
        cmdline = p.read_text().strip()
        cmdline = cmdline.replace("\x00", " ")
        parts = cmdline.split(" ")
        if parts and parts[0]:
            return parts[0]
        else:
            p_comm = p.parent / "comm"
            if p_comm.exists():
                comm = p_comm.read_text().strip()
                if comm:
                    return comm
    return str(pid)


def main():
    cpus = multiprocessing.cpu_count()
    data = []

    art_so = "/apex/com.android.art/lib64/libart.so"
    gc_sym = "_ZN3art2gc9collector16GarbageCollector3RunENS0_7GcCauseEb"

    b = BPF(text=bpf_text, cflags=["-DNUM_CPUS={}".format(cpus)])

    def store_event(_cpu, datum, _size):
        nonlocal data
        data.append(b["events"].event(datum))

    b["events"].open_perf_buffer(store_event)

    cycle_events = b["cycle_events"]
    cycle_events.open_perf_event(
        bcc.PerfType.HARDWARE, bcc.PerfHWConfig.CPU_CYCLES)
    b.attach_uprobe(name=art_so, sym=gc_sym, fn_name="gc_run")
    b.attach_uretprobe(name=art_so, sym=gc_sym, fn_name="gc_run_ret")

    def print_stats(fd=None):
        if not fd:
            fd = sys.stdout

        nonlocal data

        for datum in data:
            pid = datum.pid
            comm = datum.comm.decode("ascii")
            print("thread_group_cycles,{},{},{}".format(
                pid, comm, datum.total_cycles), file=fd)
            print("gc_cycles,{},{},{}".format(
                pid, comm, datum.gc_cycles), file=fd)

        print(file=fd)

        nonlocal b
        nonlocal cycle_events
        del cycle_events

        thread_group_cycles_total = b["thread_group_cycles_total"]
        for tgid, cycles in sorted(thread_group_cycles_total.items(), key=lambda x: x[0].value):
            print("thread_group_cycles,{},{},{}".format(
                tgid.value, render_tgid(tgid.value), cycles.value), file=fd)

        gc_cycles_total = b["gc_cycles_total"]
        for tgid, cycles in sorted(gc_cycles_total.items(), key=lambda x: x[0].value):
            print("gc_cycles,{},{},{}".format(
                tgid.value, render_tgid(tgid.value), cycles.value), file=fd)

    def finish_up(*_args):
        if len(sys.argv) >= 2:
            log_path = Path(sys.argv[1])
            with log_path.open("w") as fd:
                print_stats(fd)
            symlink = log_path.resolve().parent / "latest.out"
            if symlink.is_symlink():
                symlink.unlink()
            # Make symlink point to log_path
            # Note that Path.link_to has completely opposite semantics
            symlink.symlink_to(log_path)
        else:
            print_stats()
        exit(0)

    signal.signal(signal.SIGTERM, finish_up)
    signal.signal(signal.SIGINT, finish_up)

    print(os.getpid())

    while True:
        b.perf_buffer_poll()


if __name__ == "__main__":
    main()
