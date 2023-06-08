#!/bin/bash

#cftpput -z -u vboostadmin -p vboost12345 vboost.com "httpdocs/tn" /home/vboost/site/media/atc/images/*/output/*
user=vboostadmin
pass=vboost12345
host=vboost.com
dir=httpdocs/tn

ROOT=/data/media/atc/images
for directory in `ls $ROOT`; do
	archive=$ROOT/$directory/archive
	output=$ROOT/$directory/output
	temp=$ROOT/$directory/temp

	images=`ls $output`
	if [[ -n "$images" ]]; then
		mv $output/* $temp     # Move to temp
		cp -f $temp/* $archive # And copy to archive

		# And upload
		ncftpput -DD -z -u $user -p $pass $host $dir $temp/*
	fi
done
