#!/bin/sh

echo "***********************************"
echo " "
path=$PATH
echo $path
crontab -l > crontab_efinder
echo $PATH >> crontab_efinder
echo "@reboot sleep 10 && env DISPLAY=:0 venv-efinder/bin/python ~/Solver/eFinder.py &">> crontab_efinder
crontab < crontab_efinder
rm crontab_efinder #get rid of temp file.
exit
