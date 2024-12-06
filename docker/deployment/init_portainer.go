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
    initFlagFilePath   = "/data/init.flag"
)

type Credentials struct {
    Username string `json:"username"`
    Password string `json:"password"`
}

func main() {
    // 检查初始化标志文件是否存在
    initFlagExists := fileExists(initFlagFilePath)
    credentialFileExists := fileExists(credentialFilePath)

    if initFlagExists || credentialFileExists {
        log.Println("Initialization has already been completed by another instance or credentials are present.")
        startPortainer()
        return
    }

    // 启动 Portainer
    // cmd := exec.Command("/portainer")
    cmd := exec.Command("/portainer", os.Args[1:]...)
    cmd.Stdout = os.Stdout
    cmd.Stderr = os.Stderr

    if err := cmd.Start(); err != nil {
        log.Fatalf("Failed to start Portainer: %v", err)
    }

    // 等待 Portainer 启动
    waitForPortainer()

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
                // 创建初始化标志文件
                if err := ioutil.WriteFile(initFlagFilePath, []byte("initialized"), 0644); err != nil {
                    log.Fatalf("Failed to create initialization flag file: %v", err)
                }
            }
        }
    }

    // 等待 Portainer 进程结束
    if err := cmd.Wait(); err != nil {
        log.Fatalf("Portainer process exited with error: %v", err)
    }
}

func fileExists(filePath string) bool {
    if _, err := os.Stat(filePath); err == nil {
        return true
    }
    return false
}

func startPortainer() {
    cmd := exec.Command("/portainer")
    cmd.Stdout = os.Stdout
    cmd.Stderr = os.Stderr

    if err := cmd.Start(); err != nil {
        log.Fatalf("Failed to start Portainer: %v", err)
    }

    // 等待 Portainer 进程结束
    if err := cmd.Wait(); err != nil {
        log.Fatalf("Portainer process exited with error: %v", err)
    }
}

func waitForPortainer() {
    timeout := time.Duration(60) * time.Second
    start := time.Now()

    for {
        resp, err := http.Get(portainerURL + "/system/status")
        if err == nil && resp.StatusCode == http.StatusOK {
            fmt.Println("Portainer is up!")
            break
        }

        if time.Since(start) > timeout {
            fmt.Println("Timeout waiting for Portainer")
            os.Exit(1)
        }

        fmt.Println("Waiting for Portainer...")
        time.Sleep(2 * time.Second)
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
        var req *http.Request
        var err error

        if body != nil {
            req, err = http.NewRequest(method, url, bytes.NewBuffer(body.Bytes()))
        } else {
            req, err = http.NewRequest(method, url, nil)
        }

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