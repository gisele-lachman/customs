# Checker results

10 situations, each run once; the Checker was applied to that same agent output.

## Totals

| | count | share of tips |
|---|---|---|
| Tips from the agent (before) | 45 | 100% |
| Removed by the code check | 3 | 7% |
| Removed by the model check | 3 | 7% |
| Kept (shown) | 39 | 87% |
| ...of which tagged "partly supported" | 25 | 56% |

- Runs with errors: 0
- Runs where the model check did not finish (not fully checked): 0
- Agent cost: $0.01007 total, $0.00101 per run
- Checker cost: $0.00134 total, $0.00013 per run (12% of the total)
- Average seconds: agent 22.3, checker 2.1

## Per situation

| situation | before | code removed | model removed | partly | kept | agent $ | checker $ | seconds |
|---|---|---|---|---|---|---|---|---|
| Business dinner with my client's boss in Seoul | 7 | 0 | 1 | 3 | 6 | 0.00124 | 0.00020 | 20.28 |
| Attending a wedding in India | 6 | 1 | 1 | 2 | 4 | 0.00089 | 0.00016 | 22.53 |
| Meeting my partner's parents in Lagos | 3 | 2 | 0 | 1 | 1 | 0.00101 | 0.00007 | 56.0 |
| Attending a funeral in Nauru | 0 | 0 | 0 | 0 | 0 | 0.00076 | 0.00000 | 27.2 |
| Invited to a family celebration in Bhutan | 5 | 0 | 0 | 3 | 5 | 0.00106 | 0.00016 | 17.27 |
| First business meeting with a German company in Munich | 4 | 0 | 1 | 1 | 3 | 0.00100 | 0.00014 | 16.66 |
| Casual dinner at a friend's home in Mexico City | 4 | 0 | 0 | 3 | 4 | 0.00081 | 0.00014 | 21.68 |
| Visiting a mosque in Istanbul as a tourist | 4 | 0 | 0 | 2 | 4 | 0.00101 | 0.00014 | 17.39 |
| Having tea with my host family in Morocco | 6 | 0 | 0 | 6 | 6 | 0.00113 | 0.00018 | 18.58 |
| Going to the sauna with my Finnish colleagues | 6 | 0 | 0 | 4 | 6 | 0.00115 | 0.00017 | 25.93 |

## Every removed tip

- **Business dinner with my client's boss in Seoul**, model check (not supported): "Please do not assume that alcohol is expected; follow your own comfort and your host’s cues." (Drinking culture of Korea): excerpt does not support the tip (Excerpt only notes changing drinking culture; it gives no advice about expectations.)
- **Attending a wedding in India**, code check: "At a meal, observe how those around you eat and follow the household’s preference about hands or cutlery." (Customs and etiquette in Indian dining): excerpt not found word for word on the cited page
- **Attending a wedding in India**, model check (not supported): "Choose festive, respectful clothing, and ask your host if a particular event has a dress expectation." (Indian wedding clothes): excerpt does not support the tip (Excerpt describes regional variation but gives no clothing or dress guidance.)
- **Meeting my partner's parents in Lagos**, code check: "If you are a younger man meeting Yoruba elders, follow your partner’s cue about a respectful bow or other greeting; women’s customary greeting may involve kneeling." (Prostration): excerpt not found word for word on the cited page
- **Meeting my partner's parents in Lagos**, code check: "Ask your partner how their parents prefer to be greeted, since customs depend on their family and background." (Yoruba people): excerpt not found word for word on the cited page
- **First business meeting with a German company in Munich**, model check (not supported): "If the meeting includes a meal, let the occasion and your hosts guide your choices, as cuisine differs considerably across German regions." (German cuisine): excerpt does not support the tip (Excerpt establishes regional cuisine differences, not host-guided meal choices.)

## Partly supported (kept, tagged)

- **Business dinner with my client's boss in Seoul**: "It is considered more courteous not to stand your chopsticks upright in food or make them clatter against dishes."
- **Business dinner with my client's boss in Seoul**: "Pay attention to your host’s glass and, when appropriate, offer to pour for them rather than pouring only for yourself."
- **Business dinner with my client's boss in Seoul**: "If an older guest offers you a drink, receive it with both hands and a slight bow; you may turn slightly away when drinking."
- **Attending a wedding in India**: "If eating with your hand, wash your hands beforehand and use the hand your hosts indicate or appear to use."
- **Attending a wedding in India**: "It is considered more courteous not to assume that every wedding follows Hindu rites; let the ceremony and hosts guide you."
- **Meeting my partner's parents in Lagos**: "If the family is Yoruba, greet the parents warmly; Yoruba greeting traditions place particular importance on greeting one another."
- **Invited to a family celebration in Bhutan**: "It is considered courteous to ask your hosts whether traditional dress is expected for the celebration."
- **Invited to a family celebration in Bhutan**: "Accept or try the food graciously, bearing in mind that dishes and ingredients may differ by region and household."
- **Invited to a family celebration in Bhutan**: "It is considered more courteous not to assume that every family will serve the same dishes or follow identical celebration customs."
- **First business meeting with a German company in Munich**: "Keep in mind that customs and expectations may differ by region; Bavarian businesspeople may have local preferences of their own."
- **Casual dinner at a friend's home in Mexico City**: "If you enjoy chile, try the salsa offered alongside the meal; ask your host about its heat if you are unsure."
- **Casual dinner at a friend's home in Mexico City**: "It is considered more courteous not to assume that every dish will be very spicy; Mexico’s cuisine includes a wide range of flavors."
- **Casual dinner at a friend's home in Mexico City**: "Follow your host’s lead on what is served and how the meal is arranged; home meals and dishes differ across households and regions."
- **Visiting a mosque in Istanbul as a tourist**: "Keep your voice low and be mindful that the building is an active place of worship, not solely a tourist attraction."
- **Visiting a mosque in Istanbul as a tourist**: "It is considered more courteous not to enter areas marked as restricted, or to interrupt people who are praying."
- **Having tea with my host family in Morocco**: "Accept and enjoy the tea as a gesture of welcome, and allow time for the shared moment."
- **Having tea with my host family in Morocco**: "Expect more than one serving, and take each glass as it is offered if you would like to continue."
- **Having tea with my host family in Morocco**: "Receive the tea appreciatively; the host’s preparation and offering are part of the act of hospitality."
- **Having tea with my host family in Morocco**: "Be open to the tea’s sweetness and changing flavor from one glass to the next."
- **Having tea with my host family in Morocco**: "If tea is accompanied by food, follow your hosts’ lead; communal eating is customary at social gatherings."
- **Having tea with my host family in Morocco**: "It is considered more courteous not to assume every family serves tea in precisely the same way."
- **Going to the sauna with my Finnish colleagues**: "It is considered courteous to ask your hosts about their sauna’s arrangements, including whether it is shared or separated by gender and what they prefer guests to wear."
- **Going to the sauna with my Finnish colleagues**: "If you would like the sauna hotter or more humid, ask before adding water to the stove stones."
- **Going to the sauna with my Finnish colleagues**: "Choose a lower bench if you prefer less heat, and feel free to take breaks according to your comfort."
- **Going to the sauna with my Finnish colleagues**: "Treat the invitation as a meaningful shared activity; Finnish sauna culture is part of everyday life and national identity."
