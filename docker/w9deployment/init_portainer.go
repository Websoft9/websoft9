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
	
	dirPath := "/var/websoft9"
    if _, err := os.Stat("/var"); os.IsNotExist(err) {
        err = os.Mkdir("/var", 0755)
        if err != nil {
            fmt.Println(err)
            return
        }
    }
	
    if _, err := os.Stat(dirPath); os.IsNotExist(err) {
        err = os.Mkdir(dirPath, 0755)
        if err != nil {
            fmt.Println(err)
            return
        }
    }
	
	filePath := "/var/websoft9/credential"

	_, err := os.Stat(filePath)
	if os.IsNotExist(err) {
		password := generatePassword(16)

		err := writeToFile(filePath, password)
		if err != nil {
			fmt.Println("write file error:", err)
			return
		}
	}else{
		cmd := exec.Command("./portainer")
		cmd.Run()
	}

	content, err := ioutil.ReadFile(filePath)
	if err != nil {
		fmt.Println("read file error:", err)
		return
	}

	fmt.Println("-----portainer_admin_user: admin, portainer_admin_password: " + string(content) + " ------")

	// call portainer
	cmd := exec.Command("./portainer", "--admin-password-file", filePath)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	err = cmd.Run()
	if err != nil {
		fmt.Println("error running compiled_program:", err)
		return
	}
}

func generatePassword(length int) string {
	rand.Seed(time.Now().UnixNano())

	charset := "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+{}[]:;?.,<>"

	password := make([]byte, length)
	for i := range password {
		password[i] = charset[rand.Intn(len(charset))]
	}

	return string(password)
}

func writeToFile(filePath , content string) error {

	return ioutil.WriteFile(filePath , []byte(content), 0755)
}