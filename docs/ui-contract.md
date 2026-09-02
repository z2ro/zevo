# Contrato de UI — MVP v1

Rotas: `/` Dashboard; `/species/create`; `/species/:id`; `/world`; `/world/history`; `/legacy`; `/events`. `AppShell` oferece navegação. Todas as páginas têm loading, error+retry, empty e success; polling padrão 5 s é cancelado ao desmontar e pausado com aba oculta.

Dashboard mostra planeta, geração, ambiente, contagens, espécie corrente/CTA, eventos, bots e Population/Fitness/World charts. Criação edita nome/tipo/energia/estratégia/habitat e oito sliders, mostra Points Remaining, bloqueia soma >100 e exige preview antes de confirmar. Detalhe mostra traits, snapshots e migrate/split/strategy/focus/abandon com confirmação.

World lista habitats e espécies; History fornece timeline; Events lista raridade/metadata; Legacy resume criações ACTIVE/WILD/EXTINCT, população total, World Firsts e espécies do Zero. WILD exibe “Não é mais controlada por você.”

`DevTools` só aparece quando World informa `dev_mode=true`, com +1/+10/+100/+1000 e opção de avaliar eventos. A UI consome exclusivamente `api-contract.md`, não calcula fitness nem altera backend para mascarar divergência.
