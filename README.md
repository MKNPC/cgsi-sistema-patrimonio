# IMEI Checker - ABR Telecom / Anatel

Consulta a situacao de IMEI na base oficial de aparelhos bloqueados (perda, roubo, furto, extravio) mantida pela ABR Telecom em parceria com as operadoras brasileiras.

## Funcionalidades

- Consulta unica ou **modo monitor** (--watch) para rastrear mudancas de status
- Saida formatada ou **JSON** (--json) para integracao
- Suporte a **2captcha** e **capsolver** para resolucao automatica do reCAPTCHA
- **!! DESTAQUE EM VERMELHO** quando o IMEI estiver **IMPEDIDO/BLOQUEADO**

## Como usar

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 2. Consulta simples (com captcha manual)

**AVISO:** O site exige reCAPTCHA. Sem uma chave de API, voce precisara resolver manualmente. Recomendo usar 2captcha ou capsolver.

```bash
python imei_checker.py 123456789012345 --captcha-key SUA_CHAVE_AQUI
```

### 3. Modo monitor (a cada 5 minutos)

```bash
python imei_checker.py 123456789012345 --captcha-key SUA_CHAVE --watch 300
```

### 4. Saida em JSON

```bash
python imei_checker.py 123456789012345 --captcha-key SUA_CHAVE --json
```

### 5. Usando Capsolver em vez de 2captcha

```bash
python imei_checker.py 123456789012345 --captcha-key SUA_CHAVE --captcha-service capsolver
```

## Exemplo de saida

### IMEI LIVRE:

```
IMEI: 12345678901234
Status: LIVRE
Mensagem: LIVRE - Nao encontrado na base de bloqueios
```

### IMEI IMPEDIDO (!! DESTAQUE):

```
IMEI: 12345678901234
Status: IMPEDIDO
Operadora: CLARO
Data: 05/29/2026 12:00:00
Mensagem: IMPEDIDO - Bloqueado por CLARO
```

Em modo JSON, o campo `"bloqueado": true` indica impedimento.

## Como obter chave de API para captcha

- **2captcha:** https://2captcha.com (~$3/1000 resolucoes)
- **Capsolver:** https://capsolver.com (~$2/1000 resolucoes)

O site usa reCAPTCHA v2 (chave: `6LeL974UAAAAAFZKMQ2hiqfLRLle9KTFAaAH3Ljl`).

## Aviso Legal

Este software e uma ferramenta de consulta ao servico publico oficial mantido pela ABR Telecom em conformidade com a Resolucao 477/2007 da Anatel. O uso e de responsabilidade do usuario.
