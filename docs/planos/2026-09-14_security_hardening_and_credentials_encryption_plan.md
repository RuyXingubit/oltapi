# Plano: Suite de Hardening e Segurança (Criptografia AES-256, Rate Limiting, OWASP Headers e Concorrência)

## Contexto e Objetivos
A análise de segurança do OLTAPI identificou áreas fundamentais para elevação ao padrão de produção corporativa (PCI-DSS / ISO 27001):
1. **Credenciais de Equipamentos em Texto Claro**: As senhas de OLTs e servidores de backup FTP estavam salvas em texto puro no banco relacional PostgreSQL.
2. **Ausência de Rate Limiting**: Rotas de autenticação (`/auth/login`) e comandos pesados de hardware (`/sync`, `/telemetry`, `/enrich-vlans`) estavam expostas a força bruta e saturação de CPU/VTY na OLT física.
3. **CORS e Headers de Segurança HTTP**: Configuração permissiva com `allow_origins=["*"]` e ausência de defesas contra Clickjacking, MIME-sniffing e XSS.
4. **Recuperação Operacional de Senhas para Administradores**: Atendimento ao requisito de negócio onde o administrador precisa resgatar senhas de OLTs cadastradas no passado, com controle de acesso estrito e trilha de auditoria.

## Escopo da Implementação
- **Criptografia Reversível em Repouso**: Utilização de AES-256 Fernet na camada de repositório (`SQLOLTRepository` e `SQLFTPRepository`), com migração transparente em `init_db`.
- **Endpoint Seguro de Revelação**: `POST /api/v1/olts/{id}/reveal-credentials` exclusivo para `SUPER_ADMIN` e `TENANT_ADMIN`, com log de auditoria com IP e usuário.
- **Proteção por Rate Limiting**: Biblioteca `slowapi` configurada com 5 req/min para login e 5-15 req/min para comandos de hardware.
- **OWASP Security Headers**: Injeção de `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, etc.
- **Interface Web**: Adição do botão "🔑 Senha" na tabela de OLTs e modal com temporizador de 30s para ocultação automática da senha.
