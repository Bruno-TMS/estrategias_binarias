#!/usr/bin/env python3
"""Script de diagnóstico: chama GET /deriv/auth/verify e exibe o resultado formatado.

O token nunca é exibido em texto puro (a API já retorna `token_masked`).
"""

import argparse
import json
import sys

import httpx

DEFAULT_URL = "http://localhost:8000/deriv/auth/verify"


def format_result(status_code: int, body: dict) -> str:
    """Formata a resposta do endpoint para exibição no terminal."""
    sep = "=" * 62
    lines = [sep, f" HTTP {status_code}", sep]
    if body.get("status") == "success":
        lines += [
            " Status        : SUCESSO",
            f" Login ID      : {body.get('loginid')}",
            f" Tipo de conta : {'Demo (Virtual)' if body.get('is_virtual') else 'Real'}",
            f" Saldo         : {body.get('balance')} {body.get('currency')}",
            f" Token         : {body.get('token_masked')}",
        ]
    else:
        lines += [
            " Status        : ERRO",
            f" Mensagem      : {body.get('message') or body.get('detail') or body}",
        ]
        if body.get("token_masked"):
            lines.append(f" Token         : {body['token_masked']}")
    lines.append(sep)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Testa o endpoint /deriv/auth/verify.")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"URL do endpoint (padrão: {DEFAULT_URL})")
    parser.add_argument("--token", default=None, help="Token opcional (header X-Deriv-Token).")
    parser.add_argument("--raw", action="store_true", help="Exibe o JSON bruto.")
    args = parser.parse_args()

    headers = {"X-Deriv-Token": args.token} if args.token else {}
    try:
        resp = httpx.get(args.url, headers=headers, timeout=20.0)
    except httpx.HTTPError as exc:
        print(f"[ERRO] Não foi possível contatar a API em {args.url}: {type(exc).__name__}")
        print("Inicie o servidor: uvicorn main:app --port 8000")
        return 2

    try:
        body = resp.json()
    except ValueError:
        body = {"message": resp.text[:200]}

    if args.raw:
        print(json.dumps(body, indent=2, ensure_ascii=False))
    else:
        print(format_result(resp.status_code, body))
    return 0 if resp.status_code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
