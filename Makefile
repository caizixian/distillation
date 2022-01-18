.PHONY: all clean test

CFLAGS=-O3 -fPIC -Wall -Werror
CC=gcc
JDK=/usr/lib/jvm/temurin-17-amd64
JAVAC=$(JDK)/bin/javac
JAVA=$(JDK)/bin/java
DACAPO2006JAR=/usr/share/benchmarks/dacapo/dacapo-2006-10-MR2.jar
DACAPOBACHJAR=/usr/share/benchmarks/dacapo/dacapo-9.12-bach.jar

all: libperf_statistics.so libdacapo_callback.so Dacapo2006Callback.class DacapoBachCallback.class

Dacapo2006Callback.class: Dacapo2006Callback.java
	$(JAVAC) -cp $(DACAPO2006JAR) $^

DacapoBachCallback.class: DacapoBachCallback.java
	$(JAVAC) -cp $(DACAPOBACHJAR) $^

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
	PERF_EVENTS=PERF_COUNT_HW_CPU_CYCLES LD_PRELOAD=`pwd`/libperf_statistics.so $(JAVA) -Djava.library.path=`pwd` -agentpath:`pwd`/libperf_statistics.so -cp `pwd`:$(DACAPO2006JAR) -Xms32M -Xmx32M Harness -c Dacapo2006Callback -n 5 fop
	PERF_EVENTS=PERF_COUNT_HW_CPU_CYCLES LD_PRELOAD=`pwd`/libperf_statistics.so $(JAVA) -Djava.library.path=`pwd` -agentpath:`pwd`/libperf_statistics.so -cp `pwd`:$(DACAPOBACHJAR) -Xms32M -Xmx32M Harness -c DacapoBachCallback -n 5 fop
