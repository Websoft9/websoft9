#!/bin/bash
url_list=(
  api.ipify.org
  bot.whatismyipaddress.com
  icanhazip.com
  ifconfig.co
  ident.me
  ifconfig.me
  icanhazip.com
  ipecho.net/plain
  ipinfo.io/ip
  ip.sb
  whatismyip.akamai.com
  inet-ip.info
)

curl_ip(){
  curl --connect-timeout 1 -m 2 $1 2>/dev/null 
  return $?
}

debug(){
  for x in ${url_list[*]}
    do
      curl_ip $x
    done
}

print_ip(){
  for n in ${url_list[*]}
    do
       public_ip=`curl_ip $n`
       check_ip=`echo $public_ip | awk -F"." '{print NF}'`
    if [ ! -z "$public_ip" -a $check_ip -eq "4" ]; then
       echo $public_ip
       exit 0
    fi
    done
}
#debug
print_ip
