#!/bin/sh

echo "eFinder update"
echo " "
echo "*****************************************************************************"

HOME=/home/efinder

cd $HOME

sudo -u efinder git clone https://github.com/AstroKeith/eFinder64.git

cp /home/efinder/eFinder64/Solver/*.* /home/efinder/Solver
cp /home/efinder/eFinder64/efinder.desktop /home/efinder/.config/autostart

