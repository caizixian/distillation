// Copyright 2021 Zixian Cai
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include <stdio.h>
#include <jvmti.h>
#include <string.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <time.h>
#include <assert.h>
#include <inttypes.h>
#include <err.h>
#include "perfmon/pfmlib_perf_event.h"
#include "common.h"

// #define DEBUG
#define MAX_PHASES (1<<14)
#define MAX_COUNTERS (16)
// Example range for a 3.6GHz CPU
#define FREQ_MHZ_LOW 3200
#define FREQ_MHZ_HIGH 4000
#define FREQ_CHECK 0

typedef enum CounterType {
    Time,
    PerfEvent
} CounterType;

typedef struct CounterValue {
    uint64_t raw_value;
    uint64_t aux_value;
} CounterValue;

typedef struct Counter{
    char* name;
    CounterType type;
    bool running;
    CounterValue start_value;
    uint64_t last_delta;
    uint64_t total_count;
    uint64_t count[MAX_PHASES]; // even number for mutators
    int fd;
} Counter;

static jvmtiCapabilities caps;
static jvmtiEventCallbacks callbacks;
static int current_phase = 0;
static Counter counters[MAX_COUNTERS];
static int num_counter = 0;
static Counter* time_counter;
static Counter* task_clock_counter;
static bool gathering_statistics = false;

static bool check_single_thread() {
    char buf[100];
    FILE* fd = fopen("/proc/self/status", "r");
    if(!fd)
        return false;
    int threads = -1;
    while(fgets(buf, 100, fd)) {
        // Reading stops after an EOF or a newline
        if(strncmp(buf, "Threads:", 7) != 0) {
            continue;
        }
        // Threads:\t
        char* c = buf + 9;
        sscanf(c, "%d", &threads);
        if (threads != 1) {
            printf("Threads:\t%d\n", threads);
        }
        break;
    }
    fclose(fd);
    return threads == 1;
}

Counter perf_counter_create(char* perf_event) {
    perf_event_attr_t pe;
    int ret;
    int len = strlen(perf_event);
    char* perf_event_save = calloc(len + 1, 1);
    memcpy(perf_event_save, perf_event, len);
    memset(&pe, 0, sizeof(perf_event_attr_t));
    // Include both kernel and user space
    ret = pfm_get_perf_event_encoding(perf_event, PFM_PLM0|PFM_PLM3|PFM_PLMH, &pe, NULL, NULL);
    if (ret != PFM_SUCCESS) {
        errx(1, "error creating event '%s': %s\n", perf_event, pfm_strerror(ret));
    }
    pe.size = PERF_ATTR_SIZE_VER1,
    pe.read_format = PERF_FORMAT_TOTAL_TIME_ENABLED | PERF_FORMAT_TOTAL_TIME_RUNNING;
    pe.disabled = 1;
    pe.inherit = 1;
    int fd = perf_event_open(&pe, 0, -1, -1, 0);
    if (fd == -1) {
        err(1, "perf_event_open failed");
    }
    return (Counter) {
        .name = perf_event_save,
        .type = PerfEvent,
        .running = false,
        .start_value = (CounterValue) {.raw_value = 0},
        .total_count = 0,
        .count = { 0 },
        .fd = fd
    };
}

__attribute__((constructor))
static void setup_counters() {
    bool is_single_threaded = check_single_thread();
    if (!is_single_threaded) {
        printf("Not single threaded!\n");
        printf("inherit flag of perf_event_attr_t won't work as expected\n");
        printf("Please run with LD_PRELOAD\n");
        exit(1);
    }
    char* name = malloc(8);
    strncpy(name, "time", 8);
    counters[num_counter] = (Counter) {
        .name = name,
        .type = Time,
        .running = false,
        .start_value = (CounterValue) {.raw_value = 0, .aux_value = 0},
        .total_count = 0,
        .count = { 0 },
        .fd = -1
    };
    time_counter = &counters[num_counter];
    num_counter++;

    int ret;
    ret = pfm_initialize();
    if (ret != PFM_SUCCESS) {
        errx(1, "error initializing libpfm %s\n", pfm_strerror(ret));
    }

    // This must be before all perf counters for the sanity check
    counters[num_counter] = perf_counter_create("PERF_COUNT_SW_TASK_CLOCK");
    task_clock_counter = &counters[num_counter];
    num_counter++;


    char* perf_events_env = getenv("PERF_EVENTS");
    if (perf_events_env == NULL) {
        return;
    }
    int len = strlen(perf_events_env);
    char* perf_events = calloc(len + 1, 1);
    memcpy(perf_events, perf_events_env, len);
    char* perf_event = strtok(perf_events, ",");
    while (perf_event != NULL) {
        counters[num_counter] = perf_counter_create(perf_event);
        num_counter++;
        perf_event = strtok(NULL, ",");
    }
}

static CounterValue get_current_value(Counter* c) {
    if (c->type == Time) {
        struct timespec t;
        uint64_t ns_in_s = 1e9;
        clock_gettime(CLOCK_REALTIME, &t);
        return (CounterValue) {
            .raw_value = t.tv_sec * ns_in_s + t.tv_nsec,
            .aux_value = 0
        }; 
    } else if (c->type == PerfEvent) {
        uint64_t values[3];
        memset(values, 0, sizeof(values));
        ssize_t ret = read(c->fd, values, sizeof(values));
        if (ret < sizeof(values)) {
            if (ret == -1) {
                err(1, "read failed");
            } else {
                errx(1, "Fail to read event");
            }
        }
        assert(values[1] == values[2]);
        return (CounterValue) {
            .raw_value = values[0],
            .aux_value = values[1]
        }; 
    }
    assert(false);
}

static void counter_phase_change(Counter* c, int old_phase) {
    if (c->running) {
        assert(old_phase < MAX_PHASES);
        CounterValue current_value = get_current_value(c);
        bool overflow = current_value.raw_value < c->start_value.raw_value;
        if (overflow) {
            printf("%s current value %zu prev value %zu\n", c->name, current_value.raw_value, c->start_value.raw_value);
            fflush(stdout);
            assert(!overflow);
        }
        uint64_t delta = current_value.raw_value - c->start_value.raw_value;
        c->last_delta = delta;
        c->total_count += delta;
        c->count[old_phase] += delta;
        #if FREQ_CHECK == 1
        if (c->type == PerfEvent && strncmp(c->name, "PERF_COUNT_HW_CPU_CYCLES", 24) == 0) {
            uint64_t delta_aux = current_value.aux_value - c->start_value.aux_value;
            uint64_t freq_mhz = delta / (delta_aux / 1000);
            #ifdef DEBUG
            uint64_t delta_task_clock = task_clock_counter->last_delta;
            printf("cycles %zu time_running %zu task_clock %zu freq in MHz %zu\n", delta, delta_aux, delta_task_clock, freq_mhz);
            #endif
            uint64_t normal_freq = freq_mhz >= FREQ_MHZ_LOW && freq_mhz <= FREQ_MHZ_HIGH;
            if (!normal_freq) {
                printf("cycles %zu task_clock %zu freq in MHz %zu\n", delta, delta_aux, freq_mhz);
                fflush(stdout);
                assert(normal_freq);
            }
        }
        #endif
        c->start_value = current_value;
    }
}

static void counter_start(Counter* c) {
    c->running = true;
    c->start_value = get_current_value(c);
    // Somehow PR_TASK_PERF_EVENTS_ENABLE called from harness_begin doesn't work
    if (c->type == PerfEvent) {
        ioctl(c->fd, PERF_EVENT_IOC_RESET, 0);
        ioctl(c->fd, PERF_EVENT_IOC_ENABLE, 0);
    }
}

static void counter_stop(Counter* c) {
    assert(c->running);
    counter_phase_change(c, current_phase);
    c->running = false;
    if (c->type == PerfEvent) {
        ioctl(c->fd, PERF_EVENT_IOC_DISABLE, 0);
    }
}

static double counter_get_total(Counter* c, bool merged, bool mutator) {
    if (merged) {
        if (c->type == Time) {
            return c->total_count / 1e6;
        } else {
            return c->total_count;
        }
    }
    double sum = 0;
    for (int i = mutator?0:1; i<= current_phase; i+=2) {
        sum+= c->count[i];
    }
    if (c->type == Time) {
        return sum / 1e6;
    } else {
        return sum;
    }
    
}

static void JNICALL GarbageCollectionStart(jvmtiEnv *jvmti_env) {
    #ifdef DEBUG
    printf("GarbageCollectionStart\n");
    #endif
    if (gathering_statistics) {
        for (int i = 0; i < num_counter; i++) {
            counter_phase_change(counters+i, current_phase);
        }
        current_phase++;
    }
}

static void JNICALL GarbageCollectionFinish(jvmtiEnv *jvmti_env) {
    #ifdef DEBUG
    printf("GarbageCollectionFinish\n");
    #endif
    if (gathering_statistics) {
        for (int i = 0; i < num_counter; i++) {
            counter_phase_change(counters+i, current_phase);
        }
        current_phase++;
    }
}

void harness_begin(jlong _tls) {
    gathering_statistics = true;
    for (int i = 0; i < num_counter; i++) {
        counter_start(counters+i);
    }
}

void harness_end(jlong _tls) {
    for (int i = 0; i < num_counter; i++) {
        counter_stop(counters+i);
    }
    gathering_statistics = false;
    printf("============================ Tabulate Statistics ============================\n");
    printf("pauses\ttime");
    for (int i = 0; i < num_counter; i++) {
        printf("\t%s.other\t%s.stw", counters[i].name, counters[i].name);
        Counter *c = &counters[i];
        if (c->type == PerfEvent && strncmp(c->name, "PERF_COUNT_HW_CPU_CYCLES", 24) == 0) {
            printf("\tfreq.other\tfreq.stw");
        }
    }
    printf("\n");
    printf("%d\t%.0f",
        current_phase / 2,
        counter_get_total(time_counter, true, false)
    );
    for (int i = 0; i < num_counter; i++) {
        printf("\t%.0f\t%.0f",
            counter_get_total(counters+i, false, true),
            counter_get_total(counters+i, false, false)
        );
        Counter *c = &counters[i];
        if (c->type == PerfEvent && strncmp(c->name, "PERF_COUNT_HW_CPU_CYCLES", 24) == 0) {
            printf("\t%.2f\t%.2f",
                counter_get_total(c, false, true) / counter_get_total(task_clock_counter, false, true),
                counter_get_total(c, false, false) / counter_get_total(task_clock_counter, false, false)
            );
        }
    }        
    printf("\n");
    printf("-------------------------- End Tabulate Statistics --------------------------\n");
    FILE *fd;
    fd = fopen("scratch/perf_statistics_phases.csv", "w");
    fprintf(fd, "\"mode\",\"phase\",\"counter\",\"value\"\n");
    for (int i = 0; i < num_counter; i++) {
        for (int phase = 0; phase <= current_phase; phase++) {
            if (phase % 2 == 0) {
                fprintf(fd, "\"other\"");
            } else {
                fprintf(fd, "\"stw\"");
            }
            fprintf(fd, ",%i", phase);
            fprintf(fd, ",\"%s\",%lu\n", (counters+i)->name, (counters+i)->count[phase]);
        }
    }
    fclose(fd);
}

JNIEXPORT jint JNICALL Agent_OnLoad(JavaVM *jvm, char *options, void *reserved) {
    jvmtiEnv *jvmti;
    #ifdef DEBUG
    printf("JVMTI agent for collecting GC and mutator times\n");
    #endif

    (*jvm)->GetEnv(jvm, (void**) &jvmti, JVMTI_VERSION_1_0);
    
    jvmtiError error;

    // Add capabilities
    memset(&caps, 0, sizeof(jvmtiCapabilities));
    caps.can_generate_garbage_collection_events = 1;
    error = (*jvmti)->AddCapabilities(jvmti, &caps);
    check_jvmti_error(jvmti, error, "Failed to add JVMTI capabilities");
    // Add callbacks
    memset(&callbacks, 0, sizeof(jvmtiEventCallbacks));
    callbacks.GarbageCollectionStart = &GarbageCollectionStart;
    callbacks.GarbageCollectionFinish = &GarbageCollectionFinish;
    error = (*jvmti)->SetEventCallbacks(jvmti, &callbacks, (jint) sizeof(callbacks));
    check_jvmti_error(jvmti, error, "Failed to add JVMTI callbacks");
    // Enable notifications
    error = (*jvmti)->SetEventNotificationMode(jvmti, JVMTI_ENABLE, JVMTI_EVENT_GARBAGE_COLLECTION_START, (jthread)NULL);
    check_jvmti_error(jvmti, error, "Failed to set nofication for GarbageCollectionStart");
    error = (*jvmti)->SetEventNotificationMode(jvmti, JVMTI_ENABLE, JVMTI_EVENT_GARBAGE_COLLECTION_FINISH, (jthread)NULL);
    check_jvmti_error(jvmti, error, "Failed to set nofication for GarbageCollectionFinish");

    return JNI_OK;
}
