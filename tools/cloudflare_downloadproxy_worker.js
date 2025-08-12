addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request));
});

async function handleRequest(request) {
  const url = new URL(request.url);
  let targetUrl = url.searchParams.get("url");

  // 解码URL参数并检查是否为空
  if (!targetUrl) {
    return new Response(
      "param url required",
      { status: 400 } 
    );
  }

  // 解码URL编码的字符
  targetUrl = decodeURIComponent(targetUrl);

  // 验证targetUrl是否是有效的URL
  try {
    new URL(targetUrl);
  } catch (e) {
    return new Response(
      "Invalid URL provided",
      { status: 400 }
    );
  }
  
  // 发起请求并获取原始响应
  const response = await fetch(targetUrl, { headers: request.headers });

  const contentDisposition = response.headers.get("Content-Disposition");

  let filename='file'
  if (contentDisposition) {
    const filenameMatch = contentDisposition.match(/filename\*?=["']?(?:UTF-\d['"]*)?([^;"'\n]*)/i);
    if (filenameMatch && filenameMatch[1]) {
      filename = filenameMatch[1]
        .replace(/%(?![0-9A-Fa-f]{2})/g, '%25') // 修复非法百分号
        .replace(/\\(?![trn"'\\])/g, '\\\\');   // 转义特殊字符
      try {
        filename = decodeURIComponent(filename); // 解码 URL 编码
      } catch (e) {
        console.error("Filename decode error:", e);
      }
    }
  }
  // 从 URL 提取备用文件名
  else {
    const urlPath = new URL(targetUrl).pathname;
    filename = urlPath.split("/").pop() || "file";
    // 移除查询参数和哈希
    filename = filename.split(/[?#]/)[0];
    try {
      filename = decodeURIComponent(filename);
    } catch (e) {
      console.error("URL filename decode error:", e);
    }
  }

  filename = filename
  .replace(/[\\/:\*\?"<>\|]/g, "") // 移除非法文件名字符
  .replace(/^\.+/, "")             // 移除开头的点（如 ".hidden"）
  .trim();

  // 构造新响应头
  const headers = new Headers(response.headers);
  headers.set("Content-Disposition", `attachment; filename="${filename}"`);
  headers.set("Transfer-Encoding", "chunked"); // 启用分块传输编码

  // 返回流式响应
  return new Response(response.body, {
    status: response.status,
    headers: headers
  });
}