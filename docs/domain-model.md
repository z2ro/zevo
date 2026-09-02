# Modelo de domínio — MVP v1

`World` Eos-1 possui geração/tick monotônicos, ambiente e habitats. `Habitat` contém temperatura, radiação, pH, água, energias, recursos e capacidade. O bootstrap idempotente cria Eos-1, cinco habitats, Zero e DarwinBot, WallaceBot, MendelBot, GaiaBot e ChaosBot.

`Species` contém os campos do contrato da API, oito traits inteiros `[0,100]`, população agregada, habitat e enums: tipo `AUTOTROPH|CHEMOSYNTHETIC|HETEROTROPH|PARASITIC`; status `ACTIVE|WILD|EXTINCT`; energia `SOLAR|CHEMICAL|ORGANIC|PARASITIC`; strategy `COLONIZER|COMPETITOR|RESISTANT|OPPORTUNIST|PARASITE`. PARASITIC exige energia PARASITIC e strategy PARASITE.

Persistem ainda `WorldSnapshot`, `SpeciesPopulationSnapshot`, `SpeciesTraitHistory` (causa `MUTATION|SELECTION|FOUNDER_EFFECT|ENVIRONMENTAL_PRESSURE|EVENT`), `SpeciesRelation` (`COMPETITION|PARASITISM`), `GameEvent`, `PlayerAction` e `HistoricalFlag`.

Invariantes: no máximo uma espécie ACTIVE/controlada por player (validação transacional e índice parcial); abandono muda ACTIVE para WILD e preserva creator/histórico; WILD recebe o mesmo tick; extinção é irreversível; população não negativa; histórico é append-only. Criação custa a soma das oito traits, no máximo 100, e começa com população 100. Split mantém uma espécie agregada e registra efeito fundador; uma espécie ocupa um habitat no MVP.
