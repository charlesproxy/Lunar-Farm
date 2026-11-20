"""Atalho do Lunar Farm (roda com pythonw.exe, sem janela de terminal)."""

import os
import sys

if sys.stdout is None or sys.stderr is None:
    # pythonw não tem console; qualquer print vai para o nada.
    sys.stdout = sys.stderr = open(os.devnull, "w", encoding="utf-8")

from lunar.main import main

main()
