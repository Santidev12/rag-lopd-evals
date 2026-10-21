from typer.testing import CliRunner

from rag_lopd.cli import app

runner = CliRunner()


def test_info_no_revela_las_claves() -> None:
    resultado = runner.invoke(app, ["info"])

    assert resultado.exit_code == 0
    assert "rag-lopd-evals" in resultado.stdout
    assert "sin configurar" in resultado.stdout or "configurada" in resultado.stdout


def test_una_fuente_desconocida_falla_con_un_mensaje_util() -> None:
    resultado = runner.invoke(app, ["ingest", "convenios"])

    assert resultado.exit_code != 0
    assert "fuente desconocida" in resultado.output
    assert "lopdgdd" in resultado.output
