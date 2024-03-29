package main

import (
	"fmt"
	"io/ioutil"
	"math/rand"
	"os"
	"os/exec"
	"time"
)

func main() {
	
	filePath := "/data/credential"
	initPath := "/data/init" 

	_, err := os.Stat(filePath)
	if os.IsNotExist(err) {

		_, err := os.Stat(initPath)

		if os.IsNotExist(err) {
			fmt.Println("credential is not exist, create it.")
			password := generatePassword(16)
			err := writeToFile(filePath, password)
			if err != nil {
				fmt.Println("write file error:", err)
				return
			}
		} else {
			fmt.Println("credential is exist, skip it.")
		}

		// call portainer
		cmd := exec.Command("./portainer", "--admin-password-file", filePath, "--hide-label", "owner=websoft9")
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
	
		err = cmd.Run()
		if err != nil {
			fmt.Println("error running compiled_program:", err)
			return
		}else{
			os.Create(initPath)
		}
	}else{
		fmt.Println("credential is exist, skip it.")
		cmd := exec.Command("./portainer", "--hide-label", "owner=websoft9")
		cmd.Run()
	}

}

func generatePassword(length int) string {
	rand.Seed(time.Now().UnixNano())

	charset := "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@$()_"

	password := make([]byte, length)
	for i := range password {
		password[i] = charset[rand.Intn(len(charset))]
	}

	return string(password)
}

func writeToFile(filePath , content string) error {

	return ioutil.WriteFile(filePath , []byte(content), 0755)
}