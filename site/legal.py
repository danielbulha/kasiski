"""Textos legais do site (LGPD). Revise com atenção antes de publicar: dados do controlador em conteudo.EMPRESA."""
import html

esc = html.escape


def _controlador(E):
    partes = [f"<b>{esc(E['razao'])}</b>"]
    if E.get("cnpj"):
        partes.append(f"CNPJ {esc(E['cnpj'])}")
    if E.get("endereco"):
        partes.append(esc(E["endereco"]))
    return ", ".join(partes)


def privacidade(E):
    return f"""
<p>Esta Política explica como o Kasiski Public Market Intelligence (“Kasiski”) trata dados pessoais no site kasiski.com.br, nas
ferramentas gratuitas e na plataforma, conforme a Lei 13.709/2018 (Lei Geral de Proteção de Dados — LGPD).</p>
<h2>1. Quem é o controlador</h2>
<p>O controlador dos dados é {_controlador(E)}. Contato do encarregado ({esc(E['encarregado'])}):
<a href="mailto:{esc(E['email_privacidade'])}">{esc(E['email_privacidade'])}</a>.</p>
<h2>2. Quais dados tratamos</h2>
<ul>
<li><b>Cadastro e conta:</b> nome, e-mail, telefone, senha (guardada apenas como hash), dados da empresa (razão social, CNPJ, CNAEs, UFs de atuação).</li>
<li><b>Ferramentas gratuitas e formulários:</b> nome, e-mail, empresa, cargo, WhatsApp e mensagem que você informar; o PDF do edital enviado para análise; CNPJs consultados.</li>
<li><b>Conteúdo que você envia à plataforma:</b> editais, documentos do cofre, propostas, contratos e documentos de concorrentes. Esses arquivos podem conter dados pessoais de terceiros (por exemplo, sócios e responsáveis técnicos), tratados por você como controlador e por nós como operador para prestar o serviço.</li>
<li><b>Navegação e origem:</b> identificador aleatório do navegador, páginas visitadas, origem da visita (parâmetros UTM, site de origem, código de parceiro), eventos de uso da plataforma e endereço IP (guardado apenas de forma cifrada, para limitar abusos).</li>
<li><b>Pagamento:</b> dados de cobrança processados pelo Mercado Pago. Não recebemos nem guardamos o número do cartão.</li>
</ul>
<h2>3. Para que usamos e com qual base legal</h2>
<ul>
<li><b>Prestar o serviço contratado</b> (conta, análises, radar, alertas, cobrança) — execução de contrato (art. 7º, V).</li>
<li><b>Entregar o resultado das ferramentas gratuitas e responder contatos</b> — procedimentos preliminares a contrato, a pedido do titular (art. 7º, V).</li>
<li><b>E-mails de orientação sobre o uso da plataforma e do teste grátis</b> — legítimo interesse (art. 7º, IX), com descadastro em um clique em todo e-mail.</li>
<li><b>Newsletter Kasiski Intelligence</b> — consentimento (art. 7º, I), com confirmação por e-mail e descadastro a qualquer tempo.</li>
<li><b>Medição própria de uso do site</b> (sem compartilhar com terceiros) — legítimo interesse (art. 7º, IX); você pode desativá-la em <a href="#" data-preferencias-cookies>Preferências de cookies</a>.</li>
<li><b>Cookies de medição de terceiros e de marketing</b> (Google Analytics, Google Ads, LinkedIn, Meta) — consentimento (art. 7º, I), só depois da sua escolha no banner.</li>
<li><b>Segurança, prevenção a fraudes e abusos e cumprimento de obrigações legais</b> (inclusive guarda de registros de acesso por 6 meses, Lei 12.965/2014, art. 15) — obrigação legal (art. 7º, II) e legítimo interesse.</li>
</ul>
<h2>4. Com quem compartilhamos</h2>
<p>Com prestadores que operam dados em nosso nome, na medida necessária: hospedagem e banco de dados (Render e Netlify),
inteligência artificial (Anthropic, OpenAI e Google, para gerar análises e textos), envio de e-mails (Resend), pagamentos (Mercado Pago)
e, se você consentir, ferramentas de medição e anúncios (Google, LinkedIn, Meta). Consultamos bases públicas (Receita Federal via BrasilAPI,
PNCP, TCU, Portal da Transparência) para montar dossiês. Não vendemos dados pessoais.</p>
<h2>5. Transferência internacional</h2>
<p>Alguns desses prestadores armazenam ou processam dados fora do Brasil. Nesses casos, a transferência se apoia nas hipóteses do art. 33 da LGPD,
como cláusulas contratuais e garantias de proteção oferecidas pelos prestadores.</p>
<h2>6. Por quanto tempo guardamos</h2>
<ul>
<li><b>Conta e conteúdo:</b> enquanto a conta estiver ativa; depois do encerramento, pelo prazo necessário a obrigações legais e ao exercício de direitos (em regra, até 5 anos).</li>
<li><b>PDF enviado à análise gratuita:</b> apagado em 7 dias, salvo se você criar conta com o mesmo e-mail e o edital for importado para ela.</li>
<li><b>Registros de acesso:</b> 6 meses. <b>Dados de leads e newsletter:</b> até o descadastro ou 24 meses sem interação.</li>
</ul>
<h2>7. Seus direitos</h2>
<p>Você pode pedir confirmação do tratamento, acesso, correção, anonimização, bloqueio ou eliminação, portabilidade, informação sobre
compartilhamentos e revogação do consentimento (art. 18 da LGPD), pelo e-mail <a href="mailto:{esc(E['email_privacidade'])}">{esc(E['email_privacidade'])}</a>.
Também é possível reclamar à Autoridade Nacional de Proteção de Dados (ANPD).</p>
<h2>8. Segurança</h2>
<p>Usamos conexão cifrada (HTTPS), senhas com hash, controle de acesso por conta, verificação de e-mail no cadastro e bloqueio após tentativas
de login malsucedidas. Nenhum sistema é totalmente imune; se houver incidente relevante, comunicaremos os titulares e a ANPD conforme a lei.</p>
<h2>9. Cookies</h2>
<p>Veja a <a href="/cookies/">Política de Cookies</a> e ajuste suas escolhas em <a href="#" data-preferencias-cookies>Preferências de cookies</a>.</p>
<h2>10. Alterações</h2>
<p>Podemos atualizar esta Política. A data da última atualização fica no topo da página; mudanças relevantes serão avisadas por e-mail ou na plataforma.</p>"""


def cookies(E):
    linhas = [
        ("Necessários", "certame_token", "Armazenamento local (app)", "Mantém você conectado à plataforma", "Até sair da conta"),
        ("Necessários", "kasiski_consentimento", "Kasiski (.kasiski.com.br)", "Guarda suas escolhas de cookies no site e no app", "12 meses"),
        ("Medição própria", "kasiski_visitante", "Kasiski (.kasiski.com.br)", "Identificador aleatório do navegador para medir o uso do site e ligar a visita ao cadastro", "13 meses"),
        ("Medição própria", "kasiski_primeiro_toque / kasiski_ultimo_toque", "Kasiski (.kasiski.com.br)", "Origem da visita (UTM, site de origem, parceiro)", "13 meses"),
        ("Necessários", "kasiski_cadastro", "Kasiski (.kasiski.com.br)", "Nome e e-mail digitados nas ferramentas grátis, para pré-preencher o cadastro no app", "2 dias"),
        ("Medição (terceiros)", "_ga, _ga_*", "Google Analytics", "Estatísticas de uso do site", "Até 2 anos"),
        ("Marketing", "_gcl_au, _gcl_*", "Google Ads", "Medir conversões de anúncios", "90 dias"),
        ("Marketing", "li_sugr, bcookie, lidc, UserMatchHistory", "LinkedIn", "Insight Tag: conversões e públicos", "Até 6 meses"),
        ("Marketing", "_fbp", "Meta", "Pixel: conversões e públicos", "90 dias"),
    ]
    tabela = "".join(f"<tr><td>{esc(a)}</td><td><code>{esc(b)}</code></td><td>{esc(c)}</td><td>{esc(d)}</td><td>{esc(e)}</td></tr>" for a, b, c, d, e in linhas)
    return f"""
<p>Cookies e tecnologias semelhantes (como o armazenamento local do navegador) guardam pequenas informações no seu dispositivo.
Usamos três categorias, e você escolhe as duas últimas no banner ou em <a href="#" data-preferencias-cookies>Preferências de cookies</a>.</p>
<h2>Categorias</h2>
<ul><li><b>Necessários:</b> fazem o site e a plataforma funcionarem (login, segurança, suas escolhas). Sempre ativos.</li>
<li><b>Medição:</b> entender como o site é usado. A medição própria do Kasiski (sem compartilhamento) fica ativa, salvo se você desativar;
a medição de terceiros (Google Analytics) só com o seu consentimento.</li>
<li><b>Marketing:</b> medir campanhas e mostrar anúncios relevantes no Google, no LinkedIn e na Meta. Só com o seu consentimento.</li></ul>
<p>Usamos o Modo de Consentimento do Google: enquanto você não autoriza, as tags do Google funcionam sem gravar cookies de medição ou de anúncios.</p>
<h2>Lista</h2>
<div class="s-tabela"><table><thead><tr><th>Categoria</th><th>Nome</th><th>Origem</th><th>Finalidade</th><th>Duração</th></tr></thead><tbody>{tabela}</tbody></table></div>
<h2>Como mudar sua escolha</h2>
<p>Clique em <a href="#" data-preferencias-cookies>Preferências de cookies</a> (também no rodapé). Você pode ainda apagar os cookies nas configurações do navegador.
Dúvidas: <a href="mailto:{esc(E['email_privacidade'])}">{esc(E['email_privacidade'])}</a>.</p>"""


def termos(E):
    return f"""
<p>Estes Termos regem o uso do Kasiski, plataforma de inteligência para licitações e contratos públicos oferecida por {_controlador(E)}.
Ao criar uma conta ou usar as ferramentas gratuitas, você concorda com eles.</p>
<h2>1. O serviço</h2>
<p>O Kasiski reúne informações públicas (como o PNCP) e documentos enviados por você e usa inteligência artificial para buscar oportunidades,
analisar editais, organizar documentos, apoiar a formação de preços, gerar minutas e acompanhar contratos. As funcionalidades variam conforme o plano.</p>
<h2>2. Conta</h2>
<p>Você deve informar dados verdadeiros, manter a senha em sigilo e responder pelo uso da conta. O cadastro de empresas deve ser feito por quem
tem poderes para representá-las ou autorização para tanto.</p>
<h2>3. Teste grátis, planos e pagamento</h2>
<p>O teste grátis dura 7 dias, com os limites informados na página de planos. Os planos pagos são mensais ou anuais, cobrados pelo Mercado Pago.
Assinaturas com cartão renovam automaticamente até o cancelamento; pagamentos por Pix ou boleto valem pelo ciclo pago. O cancelamento pode ser
feito a qualquer momento em “Plano e conta”, com acesso mantido até o fim do período pago. Quando a contratação for regida pelo Código de Defesa
do Consumidor, fica assegurado o direito de arrependimento em 7 dias (art. 49 da Lei 8.078/1990).</p>
<h2>4. Uso aceitável</h2>
<p>É proibido usar o Kasiski para fins ilícitos, enviar conteúdo de terceiros sem autorização, tentar burlar limites ou a segurança, automatizar o uso
das ferramentas gratuitas ou revender o serviço sem contrato específico.</p>
<h2>5. Responsabilidades</h2>
<p>O Kasiski é ferramenta de apoio: decisões de participar, precificar, impugnar ou recorrer são suas. Veja os <a href="/termos-ia/">Termos de uso da IA</a>.
Não garantimos resultado em licitações nem a disponibilidade ininterrupta de fontes públicas de terceiros. Na máxima extensão permitida em lei,
a responsabilidade do Kasiski fica limitada ao valor pago nos 12 meses anteriores ao evento.</p>
<h2>6. Propriedade intelectual e conteúdo</h2>
<p>O software, a marca e os modelos do Kasiski são protegidos. Os documentos que você envia continuam seus; você nos autoriza a tratá-los apenas para
prestar o serviço, conforme a <a href="/privacidade/">Política de Privacidade</a>.</p>
<h2>7. Serviço de advogado</h2>
<p>A elaboração ou revisão de peças por advogado, quando contratada, é prestada por profissional habilitado na OAB, com escopo e preço informados no pedido.</p>
<h2>8. Alterações e foro</h2>
<p>Podemos alterar estes Termos, com aviso prévio de mudanças relevantes. Fica eleito o foro da {esc(E['foro'])}, ressalvadas as regras de competência
do Código de Defesa do Consumidor quando aplicável. Contato: <a href="mailto:{esc(E['email_contato'])}">{esc(E['email_contato'])}</a>.</p>"""


def termos_ia(E):
    return f"""
<p>O Kasiski usa modelos de inteligência artificial de terceiros para ler documentos e gerar análises, sugestões e minutas. Estes termos explicam
o que isso significa para você.</p>
<h2>1. A IA pode errar</h2>
<p>Modelos de linguagem podem omitir informações, interpretar mal cláusulas ou citar fundamentos de forma imprecisa. Por isso, o Kasiski submete
cláusulas restritivas e riscos a uma verificação cruzada por um segundo modelo e mostra a página do edital de origem sempre que possível. Ainda assim,
<b>confira os pontos relevantes no documento original</b> antes de decidir.</p>
<h2>2. Não substitui assessoria jurídica</h2>
<p>Análises, notas de participação, recomendações Go/No-Go e minutas de peças são apoio à decisão e não constituem parecer jurídico.
Para casos relevantes, contrate a revisão por advogado disponível na plataforma ou seu próprio advogado.</p>
<h2>3. Seus documentos</h2>
<p>Os documentos são enviados aos provedores de IA (Anthropic, OpenAI e Google) apenas para gerar a resposta solicitada, pelas interfaces comerciais
de programação (API). O Kasiski não usa seus documentos para treinar modelos próprios. Não envie dados pessoais sensíveis que não sejam necessários à análise.</p>
<h2>4. Ferramentas gratuitas</h2>
<p>A análise gratuita de edital é uma triagem resumida, com limites de uso por pessoa e por dia. O arquivo é apagado em 7 dias, salvo se importado
para uma conta criada com o mesmo e-mail.</p>
<h2>5. Dúvidas</h2>
<p><a href="mailto:{esc(E['email_contato'])}">{esc(E['email_contato'])}</a></p>"""


def paginas(E):
    return [
        ("/privacidade/", "Política de Privacidade", "Como o Kasiski trata dados pessoais conforme a LGPD: dados coletados, finalidades, bases legais, compartilhamento e direitos.", privacidade(E)),
        ("/cookies/", "Política de Cookies", "Cookies e tecnologias semelhantes usados no Kasiski: categorias, lista, finalidades e como mudar sua escolha.", cookies(E)),
        ("/termos/", "Termos de Uso", "Termos de uso da plataforma Kasiski: serviço, conta, planos, pagamento, cancelamento e responsabilidades.", termos(E)),
        ("/termos-ia/", "Termos de Uso da Inteligência Artificial", "Como o Kasiski usa inteligência artificial, limites das análises e tratamento dos documentos enviados.", termos_ia(E)),
    ]
