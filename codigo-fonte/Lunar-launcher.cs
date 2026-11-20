// Lançador do Lunar Farm (versão portátil). Não faz nada além de abrir:
//   <pasta do exe>\python\pythonw.exe "<pasta do exe>\app\Lunar.pyw" [argumentos]
// Sem rede, sem registro, sem baixar nada. Compilado com o csc.exe do .NET Framework do próprio Windows:
//   C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /target:winexe /win32icon:app\lunar\static\icon.ico /out:"Lunar Farm.exe" Lunar-launcher.cs
using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Windows.Forms;

static class Lancador
{
    [STAThread]
    static void Main(string[] args)
    {
        string pasta = AppDomain.CurrentDomain.BaseDirectory;
        string python = Path.Combine(pasta, "python", "pythonw.exe");
        string script = Path.Combine(pasta, "app", "Lunar.pyw");
        if (!File.Exists(python) || !File.Exists(script))
        {
            MessageBox.Show("Não achei python\\pythonw.exe ou app\\Lunar.pyw ao lado deste .exe.",
                            "Lunar Farm", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }
        string extras = string.Join(" ", args.Select(a => "\"" + a.Replace("\"", "\\\"") + "\""));
        try
        {
            Process.Start(new ProcessStartInfo(python, "\"" + script + "\" " + extras)
            {
                WorkingDirectory = pasta,
                UseShellExecute = true,
            });
        }
        catch (Exception e)
        {
            MessageBox.Show("Não deu para abrir o Lunar Farm:\n" + e.Message + "\n\n" + python,
                            "Lunar Farm", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
