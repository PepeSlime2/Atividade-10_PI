"""
Executa consultas SQL no MariaDB (banco fatec_iot) usando as credenciais do .env.

Instalar:  pip install pymysql python-dotenv
Rodar:     python consulta.py                          (lista as tabelas)
           python consulta.py "SELECT * FROM tabela LIMIT 10"
"""
import os
import sys

import pymysql
from dotenv import load_dotenv

load_dotenv()


def conectar():
    return pymysql.connect(
        host=os.environ["MARIADB_HOST"],
        port=int(os.environ["MARIADB_PORT"]),
        user=os.environ["MARIADB_USER"],
        password=os.environ["MARIADB_PASSWORD"],
        database=os.environ["MARIADB_DATABASE"],
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
    )


def consultar(sql, params=None):
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        if cur.description is None:      # INSERT/UPDATE/DELETE
            conn.commit()
            return cur.rowcount
        return cur.fetchall()


def main():
    sql = sys.argv[1] if len(sys.argv) > 1 else "SHOW TABLES"
    resultado = consultar(sql)

    if isinstance(resultado, int):
        print(f"{resultado} linha(s) afetada(s).")
        return
    if not resultado:
        print("(nenhum resultado)")
        return
    for linha in resultado:
        print(linha)
    print(f"\n{len(resultado)} linha(s).")


if __name__ == "__main__":
    try:
        main()
    except pymysql.MySQLError as e:
        sys.exit(f"Erro no banco: {e}")
