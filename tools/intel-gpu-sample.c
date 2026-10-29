/*
Test driver for linux/IntelGPU.c: one monotonicMs input line, one JSON sample.
*/

#include "config.h" // IWYU pragma: keep

#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#include "linux/IntelGPU.h"


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
      const IntelGPUSample* s = IntelGPU_getSample(strtoull(line, NULL, 10));
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
