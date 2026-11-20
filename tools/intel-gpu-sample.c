/*
Test driver for linux/IntelGPU.c: one monotonicMs input line, one JSON sample.
*/

#include "config.h" // IWYU pragma: keep

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include "linux/IntelGPU.h"

#ifdef INTELGPU_NO_STATX
#include <errno.h>
#include <sys/syscall.h>

/* Act like a kernel or seccomp policy without statx. A second attempt in one process
 * means the sampler did not remember that statx is missing. */
long __wrap_syscall(long number, ...);
long __wrap_syscall(long number, ...) {
#ifdef SYS_statx
   static unsigned attempts;
   if (number == SYS_statx && ++attempts == 1) {
      errno = ENOSYS;
      return -1;
   }
#endif
   /* Any other system call, or headers without SYS_statx where the sampler makes none. */
   (void)number;
   abort();
}
#endif

#ifdef INTELGPU_FAKE_TIME
#include <time.h>

static uint64_t fixtureMs;

int __wrap_clock_gettime(clockid_t clock, struct timespec* ts);
int __wrap_clock_gettime(clockid_t clock, struct timespec* ts) {
   if (clock != CLOCK_MONOTONIC)
      abort();
   ts->tv_sec = fixtureMs / 1000;
   ts->tv_nsec = (fixtureMs % 1000) * 1000000;
   return 0;
}
#endif


void CRT_done(void);
void CRT_done(void) {
}

static void printNumber(const char* key, double value) {
   if (isnan(value))
      printf(",\"%s\":null", key);
   else
      printf(",\"%s\":%.17g", key, value);
}

int main(void) {
   static const char* const statuses[] = {
      [INTELGPU_NOT_FOUND] = "not_found",
      [INTELGPU_SUSPENDED] = "suspended",
      [INTELGPU_ACTIVE] = "active",
      [INTELGPU_NO_ACCESS] = "no_access",
      [INTELGPU_UNAVAILABLE] = "unavailable",
   };
   char line[64];
   while (fgets(line, sizeof(line), stdin)) {
      uint64_t ms = strtoull(line, NULL, 10);
#ifdef INTELGPU_FAKE_TIME
      fixtureMs = ms;
#endif
      const IntelGPUSample* s = IntelGPU_getSample(ms);
      printf("{\"status\":\"%s\",\"pci\":\"%s\",\"clients\":%u,\"denied\":%u,\"memoryClients\":%u,\"videoCapacity\":%u,\"procReadable\":%s,\"procDenied\":%s,\"incomplete\":%s",
             statuses[s->status], s->pci, s->clients, s->denied, s->memoryClients, s->videoCapacity,
             s->procReadable ? "true" : "false", s->procDenied ? "true" : "false", s->incomplete ? "true" : "false");
      printNumber("usage", s->usage);
      printNumber("render", s->render);
      printNumber("compute", s->compute);
      printNumber("video", s->video);
      printNumber("videoRaw", s->videoRaw);
      printNumber("memory", s->memory);
      printNumber("clock", s->clock);
      printNumber("clockMax", s->clockMax);
      puts("}");
      fflush(stdout);
   }
   return 0;
}
