#!/bin/bash

FILE=$1

if [[ $FILE != "cityscapes" && $FILE != "night2day" && $FILE != "facades" && $FILE != "maps" && $FILE != "edges2shoes" && $FILE != "edges2handbags" ]]; then
  echo "Available datasets are: cityscapes, night2day, facades, maps, edges2shoes, edges2handbags"
  exit 1
fi

URL=http://efrosgans.eecs.berkeley.edu/pix2pix/datasets/$FILE.tar.gz
TAR_FILE=./data/$FILE.tar.gz
TARGET_DIR=./data/$FILE

mkdir -p ./data

echo "Downloading $URL..."
curl -L -C - $URL -o $TAR_FILE

if [ $? -ne 0 ]; then
  echo "Download failed. Please check your internet connection and try again."
  exit 1
fi

echo "Extracting $TAR_FILE..."
tar -zxvf $TAR_FILE -C ./data

echo "Done."
