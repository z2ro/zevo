# Regras de simulação — MVP v1

Coeficientes ficam exclusivamente em `backend/app/config/game_balance.py`. Env: `SIMULATION_TICK_SECONDS=5`, `GENERATIONS_PER_TICK=1000`, `SIMULATION_RANDOM_SEED`, `DEV_MODE`.

Fitness combina compatibilidade térmica/pH/radiação, energia da fonte, água/recursos, eficiência, bônus de estratégia, competição e host; clamp `[0,2.5]`. Compatibilidade usa `clamp(1-abs(requirement-trait)/100,0,1)`. Parasita sem host recebe grande penalidade. Preview usa a mesma base, arredondada, e retorna tendência/risk sem parcelas internas.

Tick atômico: bloquear mundo e derivar PRNG de seed+tick; resolver ações; mudar ambiente; calcular interações/fitness para toda espécie viva inclusive WILD; aplicar crescimento logístico `P * rate * (fitness-1) * (1-P/K)` limitado a ±35%; mutação/seleção; geração/extinção; bots; eventos; snapshots e commit.

Mutação altera um trait em ±1..3 (±1..6 com população pequena); fixação configurável favorece benefício, permite deriva neutra e raramente dano. Split aplica mortalidade e 1–2 mudanças `FOUNDER_EFFECT`. Migração pendente tem destino, fração, duração e mortalidade. Estratégia é imediata com cooldown; focos temporários trocam reprodução por sobrevivência ou vice-versa. Competição usa população/capacidade × metabolismo × overlap. Host exige mesmo habitat, alvo vivo não parasita e score configurado. Autótrofos solares elevam O2/reduzem CO2; quimiossintéticos alteram energia química. Mesmos estado, rules_version e seed produzem o mesmo resultado.
