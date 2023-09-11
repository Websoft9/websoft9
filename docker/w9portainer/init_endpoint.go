package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/url"
	"strings"
)

type AuthResponse struct {
	JWT string `json:"jwt"`
}

type EndpointResponse struct {
	// ...
}

func main() {
	// Read the /portainer_password file
	password, err := ioutil.ReadFile("/portainer_password")
	if err != nil {
		fmt.Println("Failed to read password file:", err)
		return
	}

	// Trim whitespace and newlines from the password
	password = []byte(strings.TrimSpace(string(password)))

	// Build the request body for the /auth API
	authRequestBody := fmt.Sprintf(`{"password": "%s", "username": "admin"}`, password)

	// Perform authentication by calling the /auth API
	authURL := "http://localhost:9000/api/auth"
	resp, err := http.Post(authURL, "application/json", strings.NewReader(authRequestBody))
	if err != nil {
		fmt.Println("Failed to perform authentication:", err)
		return
	}
	defer resp.Body.Close()

	// Check the authentication response
	if resp.StatusCode != http.StatusOK {
		fmt.Println("Authentication failed:", resp.Status)
		return
	}

	fmt.Println("Authentication successful!")

	// Read the authentication response
	authResponse, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		fmt.Println("Failed to read authentication response:", err)
		return
	}

	// Parse the authentication response JSON
	var authResponseJSON AuthResponse
	if err := json.Unmarshal(authResponse, &authResponseJSON); err != nil {
		fmt.Println("Failed to parse authentication response:", err)
		return
	}

	// Extract the access token from the authentication response
	accessToken := authResponseJSON.JWT

	// Call the /endpoints API with GET method to check if data exists
	endpointsURL := "http://localhost:9000/api/endpoints"
	req, err := http.NewRequest("GET", endpointsURL, nil)
	if err != nil {
		fmt.Println("Failed to create request:", err)
		return
	}
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", accessToken))

	client := &http.Client{}
	resp, err = client.Do(req)
	if err != nil {
		fmt.Println("Failed to check endpoint data:", err)
		return
	}
	defer resp.Body.Close()

	// Read the endpoint data response
	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		fmt.Println("Failed to read endpoint data response:", err)
		return
	}

	// Check if data exists
	if len(body) > 0 {
		// Data exists, perform further operations or return
		fmt.Println("Data exists:", string(body))
		return
	}

	// Data does not exist, call the /endpoints API to get the endpoint information
        fmt.Println("Data is notexists, need to create endpoint")
	req, err = http.NewRequest("POST", endpointsURL, nil)
	if err != nil {
		fmt.Println("Failed to create request:", err)
		return
	}
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", accessToken))

	// Add form data parameters
	data := url.Values{}
	data.Set("Name", "local")
	data.Set("EndpointCreationType", "1")
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Body = ioutil.NopCloser(strings.NewReader(data.Encode()))

	resp, err = client.Do(req)
	if err != nil {
		fmt.Println("Failed to get endpoint information:", err)
		return
	}
	defer resp.Body.Close()

	// Read the endpoint information response
	body, err = ioutil.ReadAll(resp.Body)
	if err != nil {
		fmt.Println("Failed to read endpoint information response:", err)
		return
	}

	fmt.Println("Endpoint information:", string(body))
}