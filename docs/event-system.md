# Sistema de eventos — MVP v1

`EventDefinition` declara code, rarity, política de repetição, `Condition` e consequências. Condições puras compõem `All`, `Any`, `Not`; `EventEvaluator` recebe snapshot+PRNG; consequências são aplicadas pelo serviço transacional. Raridades: COMMON, UNCOMMON, RARE, LEGENDARY, WORLD_FIRST. Constraints impedem duplicação por idempotency key e `(world_id,code)` para únicos.

`GRAY_BLOOD` é LEGENDARY/histórico. Requer parasita vivo ACTIVE ou WILD, host vivo compatível no mesmo habitat, mutation rate/população/infection/transmission acima de limites e roll. DEV aumenta a chance sem ignorar pré-condições. Metadata: parasite/host ids, ambos creator ids, geração e habitat. Consequências: perda limitada do host, flag de parasitismo, pressão/mutation temporária e trait history EVENT. WILD nunca desqualifica o parasita.

World Firsts únicos por mundo: `FIRST_STABLE_LIFE` (sobrevive X gerações), `FIRST_SUCCESSFUL_PARASITE` (relação sustentável), `FIRST_MAJOR_ADAPTATION` (delta de fitness após trait). Registram player, species, geração e metadata; reserva, evento, flags e efeitos são atômicos.
