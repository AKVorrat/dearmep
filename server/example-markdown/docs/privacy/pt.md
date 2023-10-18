# Política de Privacidade do DearMEP CSAR

A tua privacidade é importante para nós. Levamos muito a sério o nosso dever de te informar como usamos os teus dados.

A entidade responsável por tratar desta instalação do software DearMEP:

```
epicenter.works - Plattform Grundrechtspolitik
Linke Wienzeile 12/19
1060 Vienna, Austria
office@epicenter.works
```

Contacto do/a responsável pela protecção de dados: <dsba@epicenter.works>

Tens o direito de aceder aos teus dados pessoais (Artigo 15.° RGPD), de os rectificar (Artigo 16.° RGPD), de os apagar (Artigo 17.° RGPD), de limitar o seu tratamento (Artigo 18.° RGPD), de te opores ao seu tratamento (Artigo 21.° RGPD) e o direito à sua portabilidade (Artigo 20.° RGPD).
Podes enviar esses pedidos para <office@epicenter.works>.
Também tens o direito a apresentar uma queixa a uma autoridade de controlo, que na Áustria é Datenschutzbehörde (<https://www.dsb.gv.at>).

Os dados pessoais que tratamos são o endereço IP de quem acede à ferramenta, o número de telefone de chamadas (quer feitas na hora, quer agendadas) e potencialmente os dados pessoais que sejam partilhados através do formulário de comentários.
Detalhamos abaixo os vários casos de uso de tratamento:

## Aceder à ferramenta (*website*)

Quando alguém acede às ferramentas DearMEP, o endereço IP do utilizador é tratado pelo nosso servidor, estabelecido na Europa.
O objectivo do tratamento do endereço IP é fazer a geolocalização da pessoa para obtermos o seu país e para previnir abusos.
O processo de geolocalização é usado para definir qual o país pré-seleccionado na selecção de país da ferramenta.
Este processo acontece localmente no nosso servidor (em memória RAM) e não requer a partilha do teu endereço IP com terceiros.
Para garantir a integridade e estabilidade do nosso serviço, retemos o endereço IP para podermos limitar a taxa de acesso (*rate-limiting*) aos nossos servidores para previnir abusos.
Esta limitação de taxa de acessos é feita na memória RAM do servidor e a informação só é retida enquanto o serviço não for reiniciado / interrompido.
Além disto, o nosso servidor também regista os 16 bits menos significativos de endereços IPv4 e os 96 bits menos significativos de endereços IPv6 durante o período em que campanha estiver a decorrer ou durante quaisquer processos penais subsequentes.
As bases legais para este tratamento são os nossos interesses legítimos (Artigo 6.° (1) (f) RGPD) e obrigações legais (Artigo 6.° (1) (c) RGPD).

## Usar a função de telefonia

Quando usas o nosso serviço para fazer chamadas telefónicas, pedimos-te o consentimento desta política de privacidade para podermos tratar o teu número de telefone.
Não obtemos ou tratamos qualquer informação sobre o conteúdo das tuas chamadas a partir do momento em que o nosso sistema estabelece a tua ligação a um Membro do Parlamento Europeu.
Usamos o fornecedor sueco 46Elks para gerir as conversas telefónicas e a sua política de privacidade aplica-se a chamadas e a mensagens de texto (SMS) (<https://46elks.com/privacy-policy>).

Em casos excepcionais também armazenamos a informação adicional necessária para a prevenção de abusos do serviço.
Isto pode incluir informação como endereços IP, números de telefone e conteúdos de mensagens.
Esta informação pode também ser recolhida de não-utilizadores, mas apenas para a prevenção de abusos do serviço.

O nosso serviço só trata números de telefone depois de ser dado o consentimento informado a esta política de privacidade, e só enquanto houver um propósito para o seu tratamento.
As bases legais para o tratamento dos números de telefone são o consentimento informado (Artigo 6.° (1) (a) RGPD).

Construímos este sistema de forma a, em muitos casos, nem sequer sabermos o teu número de telefone.

Com quatro excepções, os números de telefone são *hashed* (<https://pt.wikipedia.org/wiki/Fun%C3%A7%C3%A3o_hash>) para limitar o risco à privacidade dos utilizadores caso o servidor seja comprometido.
Os números de telefone em texto simples (não *hashed*) são só armazenados uma vez até serem confirmados via mensagem de texto (SMS) e enquanto:
1) houver um agendamento de chamadas que não foi cancelado,
2) uma chamada na hora for iniciada através do interface *web* e até ao fim dessa chamada,
3) uma mensagem de texto (SMS) com uma hiperligação para um questionário não tiver sido enviada (ver abaixo), ou
4) houver suspeita razoável de que um número telefónico possa estar a abusar do nosso sistema.

Tratamos os números de telefone caso chamadas na hora sejam feitas através do nosso sistema a um Membro do Parlamento Europeu seleccionado ou quando houver um agendamento de chamada activo em que o utilizador tenha pedido ao nosso sistema para estabelecer uma ligação telefónica a um Membro do Parlamento Europeu do seu país a certos dias e horas da semana.
Os agendamentos de chamada podem ser cancelados pelo utilizador a qualquer altura pelo interface *web* ou directamente na chamada agendada ao premir um botão.

O primeiro passo do nosso tratamento de números de telefone é enviarmos uma mensagem de texto (SMS) com um código de verificação para confirmarmos que o número de telefone introduzido no sistema está sobre o controlo do utilizador.
Códigos de verificação que não tiverem sido usados passado uma hora são apagados.
Nós limitamos o número de tentativas que um número de telefone pode tentar ser confirmado e, portanto, armazenamos os números que não foram confirmados em formato *hash*, associados ao número de tentativas de confirmação.
Armazenamos esta informação durante a duração da campanha ou em caso de abuso, durante quaisquer processos penais subsequentes, para minimizar que números de telefone de terceiros sejam inundados com códigos de verificação não solicitados.

A confirmação de um número de telefone gera um testemunho (*cookie*) no navegador do aparelho usado para interagir com o nosso serviço.
O número de telefone é armazenado nesse testemunho, que é enviado para o navegador de forma cifrada, de modo a que apenas o servidor consiga decifrar e ler o número de telefone.
A informação de autenticação é armazenada num testemunho de sessão (*session cookie*) que será apagado assim que a sessão de navegação termine.

Para finalidades de controlo de custo e depuração do sistema (*debugging*), armazenamos informação estatística anonimizada com a hora, duração, destino, e o número de telefone truncado do utilizador.
Podemos partilhar esta informação estatística anonimizada com as campanhas que utilizam esta versão do DearMEP no contexto da legislação CSAR, para que estas possam analizar o impacto que esta ferramenta teve a nível político.

Em caso de suspeita de abuso, podemos adicionar a versão *hashed* do número de telefone a um sistma de monitorização no nosso sistema.
Uma vez adicionado, caso o número de telefone seja introduzido no nosso sistema novamente, este será armazenado em texto simples (não *hashed*).
O número de telefone só será tratado durante a duração da campanha ou em caso de abuso, durante quaisquer processos penais subsequentes (Artigo 6.° (1) (c), (f) RGPD).

## Comentários sobre a chamada

Quando uma chamada dura mais do que um determinado tempo, pedimos aos utilizadores que nos deixem comentários, através de um pequeno questionário associado a essa chamada em particular.
Podemos pedir esses comentários directamente através do navegador e/ou por uma mensagem de texto (SMS) com uma hiperligação única.
Perguntamos se o utilizador acredita que conseguiu convencer com quem falou, se houve algum problema técnico e quaisquer comentários adicionais que queiram deixar.
Esta informação é associada ao Membro do Parlamento Europeu com quem falou, ao país do utilizador, e tanto ao número de telefone *hashed* como aos primeiros dígitos do seu número de telefone, que apenas revelam o indicativo de país e o fornecedor de serviço, mas não a sua subscrição individual. Fazemos a associação com o número de telefone *hashed* para podermos correlacionar respostas do mesmo utilizador.

Os comentários sobre a chamada são desenhados para ser pseudónimos para os podermos partilhar com as campanhas que utilizem esta versão do DearMEP sem termos de partilhar quaisquer dados pessoais dos utilizadores.

Na interface da ferramenta de comentários, informamos o utilizador de que se quiser ser contactado por nós, tem de nos providenciar o seu contacto na caixa de comentários adicionais.
Se o utilizador introduzir dados pessoais como o endereço de correio electrónico ou um número de telefone nessa caixa de comentários, baseamo-nos no consentimento informado como bases legais para o seu tratamento (Artigo 6.° (1) (a) RGPD).

## Transferência de dados pessoais para terceiros

Geralmente, não partilhamos a tua informação com terceiros sem consentimento explícito.
Quando usas a funcionalidade de estabelecer chamadas, temos de partilhar o teu número de telefone com o nosso fornecedor de chamadas telefónicas 46Elks (ver texto acima).
Quando esta versão do DearMEP for utilizada por campanhas no contexto da legislação CSAR, geralmente disponibilizamos acesso aos comentários sobre chamadas pseudonimizados (que pode conter dados pessoais introduzidos no campos de comentários adicionais) e informação estatística anonimizada sobre a utilização desta ferramenta.
Podes encontrar informação sobre que campanhas é que utilizam esta versão do DearMEP em <https://dearmep.eu/showcase/chatcontrol/>.
