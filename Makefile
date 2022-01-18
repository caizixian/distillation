.PHONY: all clean

CFLAGS=-O3 -fPIC
CC=gcc
JDK=/usr/lib/jvm/temurin-17-amd64

all: libperf_statistics.so

libperf_statistics.so: perf_statistics.o common.o
	$(CC) $(CFLAGS) -shared -o $@ $^ -lpfm

perf_statistics.o: perf_statistics.c
	$(CC) $(CFLAGS) -c $^ -I$(JDK)/include -I$(JDK)/include/linux/

common.o: common.c
	$(CC) $(CFLAGS) -c $^ -I$(JDK)/include -I$(JDK)/include/linux/

clean:
	rm -rf *.o *.so
