#!/bin/bash
#repo=$1
#path=$2

git_clone(){
    for r in ${1[*]}
    do
	filename=$(echo $r | cut -d '/' -f 2)
        for x in ${2[*]}
        do      
	     if [ -e $filename ]; then
		  echo "$filename was cloned successfully"                   
		  break
	     else
		  timeout -k 1 3 git clone $x/$r.git
	     fi 	
        done
    done
}

git_clone
