#!/bin/bash
C=$HOME/tb138fc/stock-fw/tmp/vendor-root/etc/sensors/config
grep -h -o -E '"(hw_platform|soc_id|platform_subtype|platform_subtype_id|hw_version)" *: *\[?[^]}]*' $C/*.json | sort | uniq -c | sort -rn | head -15
echo "== sensor drivers in configs"; ls $C | sed 's/_[0-9]*\.json$//; s/\.json$//' | sort -u | tr '\n' ' '
