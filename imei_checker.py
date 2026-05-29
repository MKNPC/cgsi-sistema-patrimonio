import re
import sys
import time
import json
import logging
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("imei_checker")

BASE_URL = "https://www.consultaaparelhoimpedido.com.br/public-web/home"


class IMEIChecker:
    def __init__(self, captcha_api_key: str = "", captcha_service: str = "2captcha"):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        })
        self.view_state = None
        self.captcha_api_key = captcha_api_key
        self.captcha_service = captcha_service

    def _extract_view_state(self, html: str) -> Optional[str]:
        soup = BeautifulSoup(html, "html.parser")
        tag = soup.find("input", {"id": "javax.faces.ViewState"})
        if tag:
            return tag.get("value")
        match = re.search(r'javax\.faces\.ViewState" value="([^"]+)"', html)
        return match.group(1) if match else None

    def accept_terms(self) -> bool:
        log.info("Aceitando termos LGPD e iniciando sessao...")
        resp = self.session.get(BASE_URL)
        if resp.status_code != 200:
            log.error(f"Falhar ao carregar pagina inicial: {resp.status_code}")
            return False

        self.view_state = self._extract_view_state(resp.text)
        if not self.view_state:
            log.error("Nao foi possivel extrair ViewState")
            return False

        log.info("Sessao iniciada com sucesso")
        return True

    def resolve_captcha(self) -> Optional[str]:
        if not self.captcha_api_key:
            log.warning("Sem chave de API para captcha. Use --captcha-key para definir.")
            return None

        sitekey = "6LeL974UAAAAAFZKMQ2hiqfLRLle9KTFAaAH3Ljl"

        if self.captcha_service == "2captcha":
            return self._resolve_2captcha(sitekey)
        elif self.captcha_service == "capsolver":
            return self._resolve_capsolver(sitekey)
        else:
            log.error(f"Servico de captcha desconhecido: {self.captcha_service}")
            return None

    def _resolve_2captcha(self, sitekey: str) -> Optional[str]:
        log.info("Resolvendo reCAPTCHA via 2captcha...")
        resp = self.session.post(
            "https://2captcha.com/in.php",
            data={
                "key": self.captcha_api_key,
                "method": "userrecaptcha",
                "googlekey": sitekey,
                "pageurl": BASE_URL,
                "json": 1,
            },
        )
        data = resp.json()
        if data.get("status") != 1:
            log.error(f"Falha ao enviar captcha: {data}")
            return None

        request_id = data["request"]
        for _ in range(60):
            time.sleep(5)
            resp = self.session.get(
                "https://2captcha.com/res.php",
                params={
                    "key": self.captcha_api_key,
                    "action": "get",
                    "id": request_id,
                    "json": 1,
                },
            )
            data = resp.json()
            if data.get("status") == 1:
                log.info("Captcha resolvido")
                return data["request"]
            if data.get("request") and "CAPCHA_NOT_READY" in str(data.get("request")):
                continue
            log.warning(f"Status captcha: {data}")

        log.error("Timeout ao aguardar captcha")
        return None

    def _resolve_capsolver(self, sitekey: str) -> Optional[str]:
        log.info("Resolvendo reCAPTCHA via Capsolver...")
        resp = self.session.post(
            "https://api.capsolver.com/createTask",
            json={
                "clientKey": self.captcha_api_key,
                "task": {
                    "type": "ReCaptchaV2TaskProxyLess",
                    "websiteURL": BASE_URL,
                    "websiteKey": sitekey,
                },
            },
        )
        data = resp.json()
        if data.get("errorId") != 0:
            log.error(f"Falha ao criar task capsolver: {data}")
            return None

        task_id = data["taskId"]
        for _ in range(60):
            time.sleep(3)
            resp = self.session.post(
                "https://api.capsolver.com/getTaskResult",
                json={"clientKey": self.captcha_api_key, "taskId": task_id},
            )
            data = resp.json()
            if data.get("status") == "ready":
                log.info("Captcha resolvido via capsolver")
                return data["solution"]["gRecaptchaResponse"]

        log.error("Timeout ao aguardar capsolver")
        return None

    def check_imei(self, imei: str, captcha_token: str) -> dict:
        log.info(f"Consultando IMEI: {imei}")

        resp = self.session.post(
            BASE_URL,
            data={
                "j_idt9": "j_idt9",
                "imeiInput": imei[:14],
                "javax.faces.ViewState": self.view_state,
                "btnSearchImei": "btnSearchImei",
                "javax.faces.source": "btnSearchImei",
                "g-recaptcha-response": captcha_token,
            },
            headers={
                "Faces-Request": "partial/ajax",
                "X-Requested-With": "XMLHttpRequest",
            },
        )

        result = {
            "imei": imei[:14],
            "bloqueado": False,
            "operadora": "",
            "data_consulta": "",
            "raw": resp.text,
        }

        if "tableResult" in resp.text:
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.select("table tbody.ui-datatable-data tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 4:
                    imei_cell = cells[0].get_text(strip=True)
                    status_cell = cells[1].get_text(strip=True).upper()
                    date_cell = cells[2].get_text(strip=True)
                    operator_cell = cells[3].get_text(strip=True)

                    result["imei_retornado"] = imei_cell
                    result["status"] = status_cell
                    result["data_consulta"] = date_cell
                    result["operadora"] = operator_cell

                    if any(w in status_cell for w in ["BLOQUEADO", "IMPEDIDO", "RESTRITO"]):
                        result["bloqueado"] = True
                        result["mensagem"] = f"IMPEDIDO - Bloqueado por {operator_cell}"
                    else:
                        result["bloqueado"] = False
                        result["mensagem"] = f"LIVRE - Sem restricoes"
        else:
            if "Nao foram encontrados registros" in resp.text or "empty" in resp.text.lower():
                result["bloqueado"] = False
                result["mensagem"] = "LIVRE - Nao encontrado na base de bloqueios"
            else:
                result["mensagem"] = "Erro ao interpretar resposta"

        if result.get("bloqueado"):
            log.warning(f"!! {result['mensagem']}")
        else:
            log.info(f"OK {result['mensagem']}")

        return result


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Consulta IMEI na base da ABR Telecom (Anatel)"
    )
    parser.add_argument("imei", help="IMEI de 14 ou 15 digitos para consultar")
    parser.add_argument(
        "--captcha-key",
        help="Chave de API do servico de captcha (2captcha ou capsolver)",
    )
    parser.add_argument(
        "--captcha-service",
        choices=["2captcha", "capsolver"],
        default="2captcha",
        help="Servico de resolucao de captcha (default: 2captcha)",
    )
    parser.add_argument("--json", action="store_true", help="Saida em JSON")
    parser.add_argument(
        "--watch",
        type=int,
        metavar="SEGUNDOS",
        help="Modo monitor: consulta a cada N segundos (ex: --watch 300 = 5min)",
    )

    args = parser.parse_args()

    imei_clean = re.sub(r"\D", "", args.imei)
    if len(imei_clean) < 14:
        log.error(f"IMEI invalido: {args.imei}. Deve ter pelo menos 14 digitos.")
        sys.exit(1)

    checker = IMEIChecker(
        captcha_api_key=args.captcha_key or "",
        captcha_service=args.captcha_service,
    )

    if not checker.accept_terms():
        sys.exit(1)

    if args.watch:
        log.info(f"Modo monitor: consultando a cada {args.watch}s")
        try:
            while True:
                token = checker.resolve_captcha()
                if not token:
                    log.error("Nao foi possivel resolver captcha, tentando novamente...")
                    time.sleep(args.watch)
                    continue

                result = checker.check_imei(imei_clean, token)

                if args.json:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    status_icon = "!!" if result.get("bloqueado") else "OK"
                    print(
                        f"[{result.get('data_consulta', '?')}] "
                        f"{status_icon} {imei_clean[:14]} -> {result.get('mensagem', '?')}"
                    )

                time.sleep(args.watch)
        except KeyboardInterrupt:
            log.info("Monitoramento interrompido pelo usuario")
    else:
        token = checker.resolve_captcha()
        if not token:
            log.error("Nao foi possivel resolver captcha")
            sys.exit(1)

        result = checker.check_imei(imei_clean, token)

        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            status = "IMPEDIDO" if result.get("bloqueado") else "LIVRE"
            print(f"IMEI: {imei_clean[:14]}")
            print(f"Status: {status}")
            if result.get("operadora"):
                print(f"Operadora: {result['operadora']}")
            if result.get("data_consulta"):
                print(f"Data: {result['data_consulta']}")
            print(f"Mensagem: {result.get('mensagem', '?')}")


if __name__ == "__main__":
    main()
