import httpx
from fastapi import Request, Response
from fastapi.responses import JSONResponse

# RFC 7230 hop-by-hop headers — не прокидываем дальше
HOP_BY_HOP = {
    "connection", "proxy-connection", "keep-alive",
    "te", "trailer", "transfer-encoding", "upgrade"
}

async def forward(request: Request, target_url: str) -> Response:
    body = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP}

    timeout = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            resp = await client.request(
                method=request.method,
                url=target_url,
                params=request.query_params,
                headers=headers,
                content=body,
            )
    except httpx.ConnectError as e:
        return JSONResponse(
            status_code=502,
            content={"error": "Bad Gateway: upstream connect error", "detail": str(e), "upstream": target_url},
        )
    except httpx.ReadTimeout as e:
        return JSONResponse(
            status_code=504,
            content={"error": "Gateway Timeout: upstream read timeout", "detail": str(e), "upstream": target_url},
        )
    except httpx.HTTPError as e:
        return JSONResponse(
            status_code=502,
            content={"error": "Bad Gateway: upstream http error", "detail": str(e), "upstream": target_url},
        )

    response_headers = [(k, v) for k, v in resp.headers.items() if k.lower() not in HOP_BY_HOP]
    return Response(content=resp.content, status_code=resp.status_code, headers=dict(response_headers))
