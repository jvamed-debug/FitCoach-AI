# Protocolo de validação do PMC contra o TrainingPeaks (§17)

Antes de tratar CTL/ATL/TSB como números de produção, é preciso demonstrar que o
cálculo local reproduz o PMC oficial. Este documento descreve como executar essa
verificação e o que fazer quando ela falha.

**Estado atual: não executado.** A API do TrainingPeaks está pendente de
aprovação, e o §18 é explícito em que o coeficiente exato usado pelo
TrainingPeaks não pode ser fechado por suposição. Até a execução com dados
oficiais, o CTL do app é um cálculo próprio coerente com o modelo de Banister —
não uma réplica verificada do PMC do TrainingPeaks.

O que já existe é o aparato de teste, exigido pelo §19 ("testes comparativos
preparados para dados oficiais"):

| Peça | Onde |
|---|---|
| Harness executável | [`backend/scripts/validate_against_tp.py`](../backend/scripts/validate_against_tp.py) |
| Testes do harness | [`backend/tests/test_tp_validation.py`](../backend/tests/test_tp_validation.py) |

---

## Como executar

### 1. Obter o dataset (§17.1–17.2)

Conta autorizada, **mais de 180 dias contínuos**. Exporte, por dia:

- `date` — data do dia no fuso do atleta
- `tss` — TSS diário oficial
- `ctl`, `atl`, `tsb` — PMC oficial daquele dia

JSON:

```json
[{"date": "2025-01-01", "tss": 87.0, "ctl": 62.14, "atl": 71.03, "tsb": -8.89}]
```

Ou CSV com cabeçalho `date,tss,ctl,atl,tsb`.

O harness **não** acessa a API: ele consome um export já obtido por quem tem
autorização. Isso mantém a validação possível sem embutir no produto suposições
sobre endpoints, granularidade ou rate limits — todas pendências do §18.

### 2. Rodar

```bash
python -m scripts.validate_against_tp dados.json --tz America/Sao_Paulo
```

### 3. Ler o resultado (§17.5)

O critério é **erro absoluto de CTL inferior a 0,5 ponto** em todos os dias
comparados. O relatório traz ainda o erro médio (viés sistemático, que distingue
divergência de algoritmo de ruído de arredondamento), os erros de ATL e TSB, e o
pior dia.

Séries com 180 dias ou menos são processadas, mas o relatório marca o resultado
como não conclusivo para liberar produção.

---

## Quando reprova: a escada de diagnóstico (§17.6)

O harness testa as sete causas **na ordem prescrita**, computacionalmente. A
ordem importa: uma causa anterior mascara as seguintes, então corrija a primeira
antes de investigar o resto.

| # | Causa | Como o harness testa |
|---|---|---|
| 1 | Fuso horário | Desloca a série ±1 dia; se o erro cai pela metade ou mais, o agrupamento diário usa outro fuso. **Interrompe a escada** — é dominante. |
| 2 | Ausência de dias com TSS zero | Recalcula sem densificar; se o erro muda, as duas fontes discordam sobre incluir dias de descanso na média. |
| 3 | Coeficiente de suavização | Varre τ de 30 a 54,5 dias e reporta o que melhor ajusta. Se não for ≈42, é pendência do §18 — **não feche por suposição**. |
| 4 | Convenção temporal do TSB | Compara o TSB oficial contra CTL−ATL do mesmo dia e do dia anterior. |
| 5 | Semeadura insuficiente | Verifica se o erro se concentra no primeiro quarto da série — sinal de que o atleta já tinha carga acumulada antes da janela. |
| 6 | Alteração de limiar | Procura saltos bruscos de erro em um dia específico: FTP alterado com recálculo retroativo na origem. |
| 7 | Arredondamento | Resíduo abaixo de 0,05 sem outra causa: diferença de precisão decimal, não de algoritmo. |

### Uma armadilha que o harness evita

As contra-hipóteses precisam usar a **mesma semeadura** do cálculo que produziu o
erro observado. Se o baseline foi semeado com CTL 45 e a contra-hipótese com
zero, a diferença entre as duas séries — que não tem nada a ver com fuso
horário — faz o teste de fuso disparar um falso positivo. `diagnose()` recebe a
semeadura por parâmetro justamente para isso, e há um teste de regressão que
prende esse comportamento.

---

## Registro (§17.7)

Ao concluir, arquive:

1. o dataset **anonimizado**;
2. a versão do algoritmo (o relatório a imprime: `fitcoach-pmc/1.0`);
3. o relatório completo, aprovado ou reprovado.

Um resultado reprovado registrado vale mais que nenhum registro: ele documenta
qual causa da escada estava em jogo e o que foi ajustado.

---

## O que a validação não resolve

Mesmo aprovada, ela demonstra apenas que duas implementações do modelo de
Banister concordam. Não valida que CTL/ATL/TSB **preveem** desempenho, prontidão
ou risco de lesão — essa é uma afirmação de outra natureza, que o §4 do contrato
proíbe o agente de fazer.
