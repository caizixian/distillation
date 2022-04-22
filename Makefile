.PHONY: all clean test

CFLAGS=-O3 -fPIC -Wall -Werror
CC=gcc
JDK=/usr/lib/jvm/temurin-17-jdk-amd64
JAVAC=$(JDK)/bin/javac
JAVA=$(JDK)/bin/java
DACAPOCHOPINJAR=/usr/share/benchmarks/dacapo/dacapo-evaluation-git-29a657f.jar

all: libperf_statistics.so libdacapo_callback.so DacapoChopinCallback.class

DacapoChopinCallback.class: DacapoChopinCallback.java
	$(JAVAC) -cp $(DACAPOCHOPINJAR) $^

libdacapo_callback.so: dacapo_callback.c
	$(CC) $(CFLAGS) -shared -o $@ $^ -I$(JDK)/include -I$(JDK)/include/linux/

libperf_statistics.so: perf_statistics.o common.o
	$(CC) $(CFLAGS) -shared -o $@ $^ -lpfm

perf_statistics.o: perf_statistics.c
	$(CC) $(CFLAGS) -c $^ -I$(JDK)/include -I$(JDK)/include/linux/

common.o: common.c
	$(CC) $(CFLAGS) -c $^ -I$(JDK)/include -I$(JDK)/include/linux/

clean:
	rm -rf *.o *.so

test:
	PERF_EVENTS=PERF_COUNT_HW_CPU_CYCLES LD_PRELOAD=`pwd`/libperf_statistics.so $(JAVA) -Djava.library.path=`pwd` -agentpath:`pwd`/libperf_statistics.so -cp `pwd`:$(DACAPOCHOPINJAR) -Xms32M -Xmx32M Harness -c DacapoChopinCallback -n 5 fop
