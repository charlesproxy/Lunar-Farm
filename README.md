# Lunar Farm

Farm de pontos da Twitch (e da Kick) para várias contas numa janela só, para Windows.
App local: um painel no navegador controla os motores de cada conta, com ícone na bandeja.

Tudo liberado, sem plano pago: contas ilimitadas, 2 lives por conta, seguir todos os
canais da lista e compra automática na loja.

## Estrutura

- `Lunar/` — app pronto para rodar. Precisa de um Python embarcado em `Lunar/python/`
  (não versionado) ao lado de `Lunar/app/`. O `Lunar Farm.exe` só abre
  `python/pythonw.exe app/Lunar.pyw`.
- `codigo-fonte/` — o mesmo código-fonte mais o `Lunar-launcher.cs` (fonte do .exe).

## Rodar a partir do código

```
python -m pip install -r Lunar/app/requirements.txt
python Lunar/app/Lunar.pyw
```

O painel abre em `http://127.0.0.1:47800/`.

## Créditos

Usa o [Twitch Channel Points Miner v2](https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2)
(GPLv3), incluído em `app/TwitchChannelPointsMiner/`.
