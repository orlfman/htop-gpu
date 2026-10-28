/*
Test driver for src/htop/linux/AMDGPU.c, built by build-sampler.sh.
Reads one monotonicMs value per stdin line, prints the matching sample as one JSON line.
*/

#include "config.h" // IWYU pragma: keep

#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#include "linux/AMDGPU.h"


/* XUtils.c's fail() calls this */
void CRT_done(void);
void CRT_done(void) {
}

static void printNumber(const char* key, double value) {
   if (isnan(value))
      printf(",\"%s\":null", key);
   else
      printf(",\"%s\":%.17g", key, value);
}

static void printArray(const char* key, const double* values, size_t count) {
   printf(",\"%s\":[", key);
   for (size_t i = 0; i < count; i++) {
      if (isnan(values[i]))
         printf("%snull", i ? "," : "");
      else
         printf("%s%.17g", i ? "," : "", values[i]);
   }
   printf("]");
}

int main(void) {
   static const char* const statusNames[] = {
      [AMDGPU_NOT_FOUND] = "not_found",
      [AMDGPU_SUSPENDED] = "suspended",
      [AMDGPU_ACTIVE]    = "active",
   };

   char line[64];
   while (fgets(line, sizeof(line), stdin)) {
      const AMDGPUSample* s = AMDGPU_getSample(strtoull(line, NULL, 10));

      printf("{\"status\":\"%s\"", statusNames[s->status]);
      if (s->card)
         printf(",\"card\":\"%s\",\"pci\":\"%s\"", s->card->name, s->pciAddress);
      else
         printf(",\"card\":null,\"pci\":null");
      printNumber("gpuBusy", s->gpuBusy);
      printNumber("memBusy", s->memBusy);
      printNumber("vcnBusy", s->vcnBusy);
      printNumber("vramUsed", s->vramUsed);
      printNumber("vramTotal", s->vramTotal);
      printNumber("power", s->power);
      printNumber("powerCap", s->powerCap);
      printArray("temp", s->temp, AMDGPU_TEMP_COUNT);
      printArray("tempCrit", s->tempCrit, AMDGPU_TEMP_COUNT);
      printNumber("sclk", s->sclk);
      printNumber("sclkPeak", s->sclkPeak);
      printNumber("mclk", s->mclk);
      printNumber("mclkMax", s->mclkMax);
      printNumber("memRate", s->memRate);
      printNumber("vclk", s->vclk);
      printNumber("dclk", s->dclk);
      printNumber("fan", s->fan);
      printNumber("fanMax", s->fanMax);
      printf("}\n");
      fflush(stdout);
   }
   return 0;
}
