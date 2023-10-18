package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"os"
	"time"
)

const (
	AdminUser     = "admin"
	EndpointURL   = "http://localhost:9000/api/endpoints"
	CredentialLoc = "/data/credential"
)

type Endpoint struct {
	Name string `json:"Name"`
	URL  string `json:"URL"`
}

func main() {
	var password string

	for {
		if _, err := os.Stat(CredentialLoc); os.IsNotExist(err) {
			fmt.Printf("%s does not exist, waiting for 3 seconds...\n", CredentialLoc)
			time.Sleep(3 * time.Second)
		} else {
			fmt.Printf("%s exists, proceeding...\n", CredentialLoc)
			data, err := ioutil.ReadFile(CredentialLoc)
			if err != nil {
				fmt.Println("Failed to read file:", err)
				return
			}
			password = string(data)
			break
		}
	}

	client := &http.Client{}
	req, err := http.NewRequest("GET", EndpointURL, nil)
	req.SetBasicAuth(AdminUser, password)
	resp, err := client.Do(req)
	if err != nil {
		fmt.Println("Failed to make request:", err)
		return
	}
	defer resp.Body.Close()

	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		fmt.Println("Failed to read response:", err)
		return
	}

	var endpoints []Endpoint
	err = json.Unmarshal(body, &endpoints)
	if err != nil {
		fmt.Println("Failed to parse JSON:", err)
		return
	}

	for _, endpoint := range endpoints {
		if endpoint.Name == "local" && endpoint.URL == "/var/run/docker.sock" {
			fmt.Println("Endpoint exists, exiting...")
			return
		}
	}

	fmt.Println("Endpoint does not exist, creating...")
	endpoint := Endpoint{
		Name: "local",
		URL:  "/var/run/docker.sock",
	}
	data, err := json.Marshal(endpoint)
	if err != nil {
		fmt.Println("Failed to encode JSON:", err)
		return
	}

	req, err = http.NewRequest("POST", EndpointURL, bytes.NewBuffer(data))
	req.SetBasicAuth(AdminUser, password)
	resp, err = client.Do(req)
	if err != nil {
		fmt.Println("Failed to make request:", err)
		return
	}

	if resp.StatusCode != http.StatusCreated {
		fmt.Println("Failed to create endpoint:", resp.Status)
	} else {
		fmt.Println("Endpoint created successfully")
	}
}
