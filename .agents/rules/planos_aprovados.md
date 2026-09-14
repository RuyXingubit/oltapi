# DIRETRIZ MANDATÓRIA: HISTÓRICO DE PLANOS E ENTREGAS APROVADOS

1. **Apenas Planos Aprovados no Repositório:**
   - Nunca polua a pasta `docs/planos/` com rascunhos, planos descartados ou versões intermediárias que não foram aceitas pelo usuário.
   - Somente quando o usuário aprovar explicitamente o plano (`implementation_plan.md`), o documento é copiado e versionado em:
     ```
     docs/planos/YYYY-MM-DD_<tema>_plan.md
     ```

2. **Walkthroughs de Conclusão Aprovados:**
   - Ao concluir a implementação e testes com aprovação do usuário, o resumo de entrega (`walkthrough.md`) deve ser arquivado junto ao plano:
     ```
     docs/planos/YYYY-MM-DD_<tema>_walkthrough.md
     ```

3. **Permanência no Git:**
   - Todos os arquivos em `docs/planos/` devem ser comitados no Git para que fiquem visíveis para a equipe e preservados contra reinicializações ou trocas de ambiente.
