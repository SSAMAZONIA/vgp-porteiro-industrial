# VGP Porteiro Industrial (Camada Bronze)

## O que faz
- Varre: Google Drive (G:\Meu Drive) + Desktop + Documents
- Gera manifesto append-only: `scan_out\catalog.jsonl`
- Mantém checkpoint/idempotência: `scan_out\state.json`
- Pitstop a cada 30 min: `scan_out\pitstop_status.txt` e `scan_out\pitstop_status.json`
- Log de erros (permissão/arquivo): `scan_out\errors.jsonl`

## Onde olhar "tá vivo?"
- `scan_out\pitstop_status.txt`
- `scan_out\pitstop_status.json`
- `scan_out\catalog.jsonl` crescendo

## Rodar
Execute:
- `.\run_porteiro.ps1`

## Links úteis (oficiais)
- tqdm: https://github.com/tqdm/tqdm
- pdfminer.six (detectar/extrair texto embutido): https://github.com/pdfminer/pdfminer.six
- PaddleOCR: https://github.com/PaddlePaddle/PaddleOCR
- DocTR: https://github.com/mindee/doctr
- GLiNER (NER): https://github.com/urchade/GLiNER
- Rust (Cargo): https://doc.rust-lang.org/cargo/

## Próxima etapa (Silver)
- Classificar por Centro de Custos (RegexSet / keywords)
- Extrair valores (planilha/PDF texto/OCR sob demanda)
- Consolidar Parquet particionado (Polars)
