set -euo pipefail
printf 'api.ipify.org: '
curl --ipv4 --fail --silent --show-error --max-time 15 https://api.ipify.org
printf '\ncheckip.amazonaws.com: '
curl --ipv4 --fail --silent --show-error --max-time 15 https://checkip.amazonaws.com
printf '\n'