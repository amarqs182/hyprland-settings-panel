# Hyprland Settings Panel — Audit v0.55.2

Data: 2026-05-20
Metodo: `hyprctl getoption <opt> -j` para cada opcao do painel

---

## Resumo

| Metrica | Valor |
|---------|-------|
| Total de opcoes no painel | 178 |
| Opcoes validas (encontradas no Hyprland) | 175 |
| Opcoes invalidas / artefatos | 3 |
| Incompatibilidades de tipo encontradas | 5 |
| Incompatibilidades corrigidas | 5 |
| Opcoes faltando no painel | 0 (todas as categorias cobertas) |

---

## Issues Corrigidos

### FIX 1: `general:gaps_workspaces` — QuadSlider → Slider
- **Problema:** Widget `makeQuadSlider` (4 sliders) mas opcao e `int` simples
- **Correcao:** Mudado para `makeSlider` (range 0-50)
- **Status:** ✅ CORRIGIDO

### FIX 2: `decoration:shadow:color` — Conversao int→hex
- **Problema:** Widget `makeText` mas valor vem como `int` (3994688026)
- **Correcao:** Adicionada funcao `intToColor()` que converte int→hex (0xeeRRGGBB) para exibicao
- **Status:** ✅ CORRIGIDO

### FIX 3: `misc:background_color` — Conversao int→hex
- **Problema:** Mesmo problema que shadow:color
- **Correcao:** Usa mesma funcao `intToColor()` 
- **Status:** ✅ CORRIGIDO

### FIX 4: `master:new_on_active` — Toggle → Select
- **Problema:** Widget `makeToggle` (bool) mas opcao e `str` (none/master/slave)
- **Correcao:** Mudado para `makeSelect(['none', 'master', 'slave'])`
- **Status:** ✅ CORRIGIDO

### FIX 5: `dwindle:force_split` — Select com comparacao de tipo
- **Problema:** Comparacao `data.value === o` falhava quando int vs string
- **Correcao:** Mudado para `String(data.value) === String(o)` em `makeSelect`
- **Status:** ✅ CORRIGIDO

---

## Artefatos (nao causam bugs, apenas grep artifacts)

| Referencia | Contexto | Acao |
|-----------|----------|------|
| `gestures:workspace_swipe` | Python default check | OK — nao e opcao hyprctl |
| `gestures:workspace_swipe_` | Artefato do grep | Ignorar |
| `compose:caps` | Exemplo no placeholder do kb_options | OK — nao e opcao |

---

## Verificacao Final

- [x] 175/178 opcoes validas no Hyprland 0.55.2
- [x] 5 incompatibilidades de tipo corrigidas
- [x] JavaScript sem erros de sintaxe
- [x] Painel carrega corretamente
- [x] API responde corretamente para todas as opcoes

---

## Status: 100% CORRIGIDO

Todas as opcoes do painel agora funcionam corretamente com Hyprland 0.55.2.
