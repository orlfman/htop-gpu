/*
Test driver for src/htop/linux/IntelRAPL.c, built by test-rapl.py.
Reads one monotonicMs value per stdin line, prints the matching sample as one JSON line.
*/

#include "config.h" // IWYU pragma: keep

#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#include "linux/IntelRAPL.h"


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

int main(void) {
   static const char* const statusNames[] = {
      [INTELRAPL_NOT_FOUND] = "not_found",
      [INTELRAPL_NO_ACCESS] = "no_access",
      [INTELRAPL_ACTIVE]    = "active",
   };

   char line[64];
   while (fgets(line, sizeof(line), stdin)) {
      const IntelRAPLSample* s = IntelRAPL_getSample(strtoull(line, NULL, 10));

      printf("{\"status\":\"%s\",\"packages\":%u", statusNames[s->status], s->packages);
      printNumber("power", s->power);
      printNumber("powerLimit", s->powerLimit);
      printf("}\n");
      fflush(stdout);
   }
   return 0;
}
