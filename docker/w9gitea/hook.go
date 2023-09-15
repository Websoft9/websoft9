package main

import (
	"fmt"
	"log"
	"net/http"
	"net/http/httputil"
)

func main() {
	http.HandleFunc("/", handleRequest)
	log.Fatal(http.ListenAndServe(":8080", nil))
}

func handleRequest(w http.ResponseWriter, r *http.Request) {
	// 打印请求行和头部信息
	requestDump, err := httputil.DumpRequest(r, true)
	if err != nil {
		log.Println("Error dumping request:", err)
		return
	}
	log.Println(string(requestDump))

	log.Println("-----------------------接口被调用了一次！---------")
	fmt.Fprintf(w, "--Hello, World!")
}