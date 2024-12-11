package main

import (
    "bytes"
    "crypto/rand"
    "encoding/json"
    "fmt"
    "io/ioutil"
    "log"
    "math/big"
    "net/http"
    "net/url"
    "os"
    "os/exec"
    "strings"
    "time"
)

const (
    portainerURL       = "http://localhost:9000/api"
    maxRetries         = 5
    retryDelay         = 5 * time.Second
    charset            = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@$()_"
    credentialFilePath = "/data/credential"
    initCheckURL       = portainerURL + "/users/admin/check"
    waitTimeout        = 60 * time.Second
    waitInterval       = 2 * time.Second
)

type Credentials struct {
    Username string `json:"username"`
    Password string `json:"password"`
}

func main() {
    // 启动并等待 Portainer 启动
    cmd, err := startAndWaitForPortainer(os.Args[1:]...)
    if err != nil {
        log.Fatalf("Failed to start and wait for Portainer: %v", err)
    }

    // 检查是否已经初始化
    if isPortainerInitialized() {
        log.Println("Portainer is already initialized.")
        // 等待 Portainer 进程结束
        if err := cmd.Wait(); err != nil {
            log.Fatalf("Portainer process exited with error: %v", err)
        }
        return
    }

    // 初始化 Portainer
    adminUsername := "admin"
    adminPassword := generateRandomPassword(12)

    if err := initializePortainerUser(adminUsername, adminPassword); err != nil {
        log.Fatalf("Failed to initialize Portainer user: %v", err)
    } else {
        if err := writeCredentialsToFile(adminPassword); err != nil {
            log.Fatalf("Failed to write credentials to file: %v", err)
        } else {
            if err := initializeLocalEndpoint(adminUsername, adminPassword); err != nil {
                log.Fatalf("Failed to initialize local endpoint: %v", err)
            } else {
                fmt.Println("Portainer initialization completed successfully.")
            }
        }
    }

    // 等待 Portainer 进程结束
    if err := cmd.Wait(); err != nil {
        log.Fatalf("Portainer process exited with error: %v", err)
    }
}

func startAndWaitForPortainer(args ...string) (*exec.Cmd, error) {
    cmd := exec.Command("/portainer", args...)
    cmd.Stdout = os.Stdout
    cmd.Stderr = os.Stderr

    if err := cmd.Start(); err != nil {
        return nil, fmt.Errorf("failed to start Portainer: %w", err)
    }

    timeout := time.After(waitTimeout)
    ticker := time.NewTicker(waitInterval)
    defer ticker.Stop()

    for {
        select {
        case <-timeout:
            return nil, fmt.Errorf("timeout waiting for Portainer")
        case <-ticker.C:
            resp, err := http.Get(portainerURL + "/system/status")
            if err == nil && resp.StatusCode == http.StatusOK {
                fmt.Println("Portainer is up……!")
                return cmd, nil
            }
            fmt.Println("Waiting for Portainer...")
        }
    }
}

func generateRandomPassword(length int) string {
    password := make([]byte, length)
    for i := range password {
        char, _ := rand.Int(rand.Reader, big.NewInt(int64(len(charset))))
        password[i] = charset[char.Int64()]
    }
    return string(password)
}

func initializePortainerUser(username, password string) error {
    requestBody := Credentials{Username: username, Password: password}
    jsonBody, err := json.Marshal(requestBody)
    if err != nil {
        return fmt.Errorf("error marshaling request body: %w", err)
    }

    resp, err := retryRequest("POST", portainerURL+"/users/admin/init", "application/json", bytes.NewBuffer(jsonBody))
    if err != nil {
        return fmt.Errorf("error making request to Portainer API: %w", err)
    }
    defer resp.Body.Close()

    if resp.StatusCode == http.StatusConflict {
        return nil
    }

    if resp.StatusCode != http.StatusOK {
        body, _ := ioutil.ReadAll(resp.Body)
        return fmt.Errorf("unexpected response status: %d, body: %s", resp.StatusCode, body)
    }

    return nil
}

func initializeLocalEndpoint(username, password string) error {
    authBody := Credentials{Username: username, Password: password}
    jsonBody, err := json.Marshal(authBody)
    if err != nil {
        return fmt.Errorf("error marshaling auth body: %w", err)
    }

    resp, err := retryRequest("POST", portainerURL+"/auth", "application/json", bytes.NewBuffer(jsonBody))
    if err != nil {
        return fmt.Errorf("error authenticating with Portainer API: %w", err)
    }
    defer resp.Body.Close()

    if resp.StatusCode != http.StatusOK {
        body, _ := ioutil.ReadAll(resp.Body)
        return fmt.Errorf("unexpected response status: %d, body: %s", resp.StatusCode, body)
    }

    var authResult map[string]string
    body, err := ioutil.ReadAll(resp.Body)
    if err != nil {
        return fmt.Errorf("error reading authentication response: %w", err)
    }

    err = json.Unmarshal(body, &authResult)
    if err != nil {
        return fmt.Errorf("error parsing authentication response: %w", err)
    }

    jwtToken := authResult["jwt"]

    endpointBody := url.Values{}
    endpointBody.Set("Name", "local")
    endpointBody.Set("EndpointCreationType", "1")

    req, err := http.NewRequest("POST", portainerURL+"/endpoints", strings.NewReader(endpointBody.Encode()))
    if err != nil {
        return fmt.Errorf("error creating endpoint request: %w", err)
    }
    req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
    req.Header.Set("Authorization", "Bearer "+jwtToken)

    client := &http.Client{}
    resp, err = client.Do(req)
    if err != nil {
        return fmt.Errorf("error creating endpoint in Portainer API: %w", err)
    }
    defer resp.Body.Close()

    if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusConflict {
        body, _ := ioutil.ReadAll(resp.Body)
        return fmt.Errorf("unexpected response status: %d, body: %s", resp.StatusCode, body)
    }

    if resp.StatusCode == http.StatusConflict {
        fmt.Println("Endpoint already exists, but this is considered a success.")
    } else {
        fmt.Println("Endpoint created successfully.")
    }

    return nil
}

func writeCredentialsToFile(password string) error {
    err := ioutil.WriteFile(credentialFilePath, []byte(password), 0755)
    if err != nil {
        return fmt.Errorf("error writing password to file: %w", err)
    }

    return nil
}

func retryRequest(method, url, contentType string, body *bytes.Buffer) (*http.Response, error) {
    client := &http.Client{}
    for i := 0; i < maxRetries; i++ {
        req, err := http.NewRequest(method, url, body)
        if err != nil {
            return nil, fmt.Errorf("error creating request: %w", err)
        }
        req.Header.Set("Content-Type", contentType)

        resp, err := client.Do(req)
        if err == nil {
            return resp, nil
        }

        log.Printf("Request failed: %v. Retrying in %v...", err, retryDelay)
        time.Sleep(retryDelay)
    }
    return nil, fmt.Errorf("max retries reached")
}

func isPortainerInitialized() bool {
    resp, err := http.Get(initCheckURL)
    if err != nil {
        log.Fatalf("Failed to check Portainer initialization status: %v", err)
    }
    defer resp.Body.Close()

    if resp.StatusCode == http.StatusNoContent {
        return true
    }

    if resp.StatusCode == http.StatusNotFound {
        return false
    }

    log.Fatalf("Unexpected response status: %d", resp.StatusCode)
    return false
}
