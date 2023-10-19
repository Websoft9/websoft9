package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/url"
	"strings"
	"os"
	"time"
)

const (
	AdminUser     = "admin"
	EndpointURL   = "http://localhost:9000/api/endpoints"
	AuthURL       = "http://localhost:9000/api/auth"
	CredentialLoc = "/data/credential"
)

type Endpoint struct {
	Name string `json:"name"`
	URL  string `json:"url"`
}

type EndpointCreation struct {
	Name string `json:"name"`
	EndpointCreationType int `json:"EndpointCreationType"`
}

type AuthResponse struct {
	Jwt string `json:"jwt"`
}

type Credentials struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

func main() {
	
	fmt.Println("Start to create endpoint...")
	client := &http.Client{}

	password, err := getPassword()
	if err != nil {
		fmt.Println("Failed to get password:", err)
		return
	}

	token, err := authenticate(client, AdminUser, password)
	if err != nil {
		fmt.Println("Failed to authenticate:", err)
		return
	}

	endpoints, err := queryEndpoints(client, token)
	if err != nil {
		fmt.Println("Failed to query endpoints:", err)
		return
	}

	for _, endpoint := range endpoints {
		if endpoint.Name == "local" && endpoint.URL == "unix:///var/run/docker.sock" {
			fmt.Println("Endpoint exists, exiting...")
			return
		}
	}

	fmt.Println("Endpoint does not exist, creating...")
	createEndpoint(client, token)

	fmt.Println("Endpoint created successfully")
}

func getPassword() (string, error) {
	for {
		if _, err := os.Stat(CredentialLoc); os.IsNotExist(err) {
			fmt.Printf("%s does not exist, waiting for 3 seconds...\n", CredentialLoc)
			time.Sleep(3 * time.Second)
		} else {
			fmt.Printf("%s exists, proceeding...\n", CredentialLoc)
			data, err := ioutil.ReadFile(CredentialLoc)
			if err != nil {
				return "", err
			}
			return string(data), nil
		}
	}
}

func authenticate(client *http.Client, username, password string) (string, error) {
	credentials := Credentials{Username: username, Password: password}
	credentialsJson, err := json.Marshal(credentials)
	if err != nil {
		return "", err
	}

	req, err := http.NewRequest("POST", AuthURL, bytes.NewBuffer(credentialsJson))
	req.Header.Set("Content-Type", "application/json")
	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}

	var authResponse AuthResponse
	err = json.Unmarshal(body, &authResponse)
	if err != nil {
		return "", err
	}

	return authResponse.Jwt, nil
}

func queryEndpoints(client *http.Client, token string) ([]Endpoint, error) {
	req, err := http.NewRequest("GET", EndpointURL, nil)
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	var endpoints []Endpoint
	err = json.Unmarshal(body, &endpoints)
	if err != nil {
		return nil, err
	}

	return endpoints, nil
}

func createEndpoint(client *http.Client, token string) error {
	data := url.Values{
		"Name":                  {"local"},
		"EndpointCreationType":  {"1"},
	}

	req, err := http.NewRequest("POST", EndpointURL, strings.NewReader(data.Encode()))
	if err != nil {
		return err
	}

	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("Authorization", "Bearer "+token)

	resp, err := client.Do(req)

	if resp.StatusCode != http.StatusCreated {
		body, _ := ioutil.ReadAll(resp.Body)
		return fmt.Errorf("Failed to create endpoint: %s, Response body: %s", resp.Status, string(body))
	}

	return nil
}