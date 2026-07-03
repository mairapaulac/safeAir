/*
 * =====================================================================
 *  SafeAir - Monitor de Qualidade Ambiental para Pessoas com Problemas
 *  Respiratorios
 *  Projeto de Fisica Experimental III
 * =====================================================================
 *
 *  Hardware:
 *   - Arduino Uno
 *   - Sensor DHT11 (3 pinos)      -> pino digital 7
 *   - LCD 16x2 com modulo I2C     -> SDA/SCL (A4/A5 no Uno)
 *   - LED azul (ATENCAO)          -> pino 3
 *   - LED vermelho (CRITICO)      -> pino 4
 *   - LED branco (IDEAL)          -> pino 6
 *   - Buzzer ativo                -> pino 2
 *   - Push button (START)         -> pino 5
 *
 *  Formato enviado pela Serial (9600 baud), uma linha por leitura:
 *      temperatura,umidade,status
 *  Exemplo:
 *      25.3,42,IDEAL
 *      26.1,28,CRITICO
 *
 *  Modos de operacao (a partir da tela "Aperte START"):
 *   - Toque rapido no botao  -> Modo NORMAL (le o DHT11 de verdade)
 *   - Segurar o botao por 2s -> Modo DEMO (simula os 4 niveis de risco
 *     automaticamente a cada poucos segundos, sem depender da umidade
 *     real do ambiente - util para testar o dashboard e apresentacoes)
 * =====================================================================
 */

#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>

// ---------------------------------------------------------------------
// Configuracao de pinos
// ---------------------------------------------------------------------
#define DHT_PIN     7
#define DHT_TYPE    DHT11

#define LED_AZUL    3   // Atencao
#define LED_VERMELHO 4  // Critico
#define LED_BRANCO  6   // Ideal
#define BUZZER_PIN  2
#define BUTTON_PIN  5

// ---------------------------------------------------------------------
// Configuracao do LCD I2C
// Endereco mais comum e 0x27. Se o LCD nao funcionar, tente 0x3F.
// ---------------------------------------------------------------------
LiquidCrystal_I2C lcd(0x27, 16, 2);

DHT dht(DHT_PIN, DHT_TYPE);

// ---------------------------------------------------------------------
// Variaveis de controle
// ---------------------------------------------------------------------
enum ModoOperacao { AGUARDANDO, NORMAL, DEMO };
ModoOperacao modo = AGUARDANDO;

bool botaoEstavaPressionado = false;
unsigned long inicioPressao = 0;
const unsigned long LIMITE_DEMO = 2000; // segurar por 2s entra em modo DEMO

unsigned long ultimaLeitura = 0;
const unsigned long INTERVALO_LEITURA = 2000; // DHT11 exige >= 1s entre leituras
const unsigned long INTERVALO_DEMO = 3000;    // troca de cenario no modo demo

unsigned long ultimoToggleBuzzer = 0;
const unsigned long INTERVALO_BUZZER = 400; // piscar/bipar em estado critico
bool buzzerLigado = false;

// Cenarios simulados no modo DEMO: um para cada faixa de status
const float DEMO_TEMPERATURA[] = {26.5, 24.0, 23.0, 25.0};
const float DEMO_UMIDADE[]     = {22,   35,   50,   75};
const int NUM_CENARIOS_DEMO = 4;
int indiceCenarioDemo = 0;

// ---------------------------------------------------------------------
// setup()
// ---------------------------------------------------------------------
void setup() {
  Serial.begin(9600);

  pinMode(LED_AZUL, OUTPUT);
  pinMode(LED_VERMELHO, OUTPUT);
  pinMode(LED_BRANCO, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP); // botao ligado ao GND, pressionado = LOW

  desligarTudo();

  lcd.init();
  lcd.backlight();

  dht.begin();
  randomSeed(analogRead(A0)); // semente para variar os valores no modo DEMO

  telaInicial();
}

// ---------------------------------------------------------------------
// loop()
// ---------------------------------------------------------------------
void loop() {
  unsigned long agora = millis();

  if (modo == AGUARDANDO) {
    detectarBotao();
    return;
  }

  if (modo == DEMO) {
    loopDemo(agora);
    return;
  }

  // modo == NORMAL ----------------------------------------------------

  // Le o sensor periodicamente, sem travar o loop com delay()
  if (agora - ultimaLeitura >= INTERVALO_LEITURA) {
    ultimaLeitura = agora;
    lerEExibir();
  }

  // Mantem o buzzer piscando enquanto o status for CRITICO
  atualizarBuzzer(agora);
}

// ---------------------------------------------------------------------
// Detecta toque rapido (Modo NORMAL) ou pressao longa >= 2s (Modo DEMO)
// no botao START, de forma nao bloqueante
// ---------------------------------------------------------------------
void detectarBotao() {
  bool pressionado = (digitalRead(BUTTON_PIN) == LOW);

  if (pressionado && !botaoEstavaPressionado) {
    // borda de descida: inicio do toque
    inicioPressao = millis();
    botaoEstavaPressionado = true;
  }

  if (pressionado && botaoEstavaPressionado) {
    if (millis() - inicioPressao >= LIMITE_DEMO) {
      modo = DEMO;
      botaoEstavaPressionado = false;
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("Modo DEMO");
      lcd.setCursor(0, 1);
      lcd.print("Simulando...");
      delay(800); // splash rapido, apenas na transicao
      lcd.clear();
    }
    return;
  }

  if (!pressionado && botaoEstavaPressionado) {
    // borda de subida: soltou o botao
    unsigned long duracao = millis() - inicioPressao;
    botaoEstavaPressionado = false;

    if (duracao >= 50) { // debounce simples
      modo = NORMAL;
      lcd.clear();
    }
  }
}

// ---------------------------------------------------------------------
// Modo DEMO: cicla pelos 4 cenarios de risco automaticamente,
// reaproveitando toda a logica de LEDs/LCD/buzzer/serial do modo normal
// ---------------------------------------------------------------------
void loopDemo(unsigned long agora) {
  if (agora - ultimaLeitura >= INTERVALO_DEMO) {
    ultimaLeitura = agora;

    float umidade = DEMO_UMIDADE[indiceCenarioDemo] + random(-2, 3);
    float temperatura = DEMO_TEMPERATURA[indiceCenarioDemo] + (random(-5, 6) / 10.0);

    String status = classificarStatus(umidade);

    atualizarLEDs(status);
    atualizarLCD(temperatura, umidade, status);
    enviarSerial(temperatura, umidade, status);

    indiceCenarioDemo = (indiceCenarioDemo + 1) % NUM_CENARIOS_DEMO;
  }

  atualizarBuzzer(agora);
}

// ---------------------------------------------------------------------
// Mostra a tela inicial no LCD (SafeAir / Aperte START)
// ---------------------------------------------------------------------
void telaInicial() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("SafeAir");
  lcd.setCursor(0, 1);
  lcd.print("Aperte START");
}

// ---------------------------------------------------------------------
// Le o DHT11, classifica o ambiente, atualiza LCD/LEDs/buzzer
// e envia a leitura pela Serial
// ---------------------------------------------------------------------
void lerEExibir() {
  float umidade = dht.readHumidity();
  float temperatura = dht.readTemperature();

  // Se a leitura falhar, o DHT11 retorna NaN - ignoramos esse ciclo
  if (isnan(umidade) || isnan(temperatura)) {
    lcd.setCursor(0, 0);
    lcd.print("Erro no sensor  ");
    lcd.setCursor(0, 1);
    lcd.print("Verifique DHT11 ");
    return;
  }

  String status = classificarStatus(umidade);

  atualizarLEDs(status);
  atualizarLCD(temperatura, umidade, status);
  enviarSerial(temperatura, umidade, status);
}

// ---------------------------------------------------------------------
// Classifica o status do ambiente de acordo com a umidade relativa
// ---------------------------------------------------------------------
String classificarStatus(float umidade) {
  if (umidade < 30) {
    return "CRITICO";     // umidade muito baixa - risco respiratorio alto
  } else if (umidade < 40) {
    return "ATENCAO";     // umidade um pouco baixa
  } else if (umidade <= 60) {
    return "IDEAL";       // faixa ideal de umidade
  } else {
    return "ALTA";        // umidade alta
  }
}

// ---------------------------------------------------------------------
// Liga o LED correspondente ao status e desliga os demais
// ---------------------------------------------------------------------
void atualizarLEDs(String status) {
  digitalWrite(LED_AZUL, LOW);
  digitalWrite(LED_VERMELHO, LOW);
  digitalWrite(LED_BRANCO, LOW);

  if (status == "CRITICO") {
    digitalWrite(LED_VERMELHO, HIGH);
  } else if (status == "ATENCAO" || status == "ALTA") {
    digitalWrite(LED_AZUL, HIGH);
  } else if (status == "IDEAL") {
    digitalWrite(LED_BRANCO, HIGH);
  }

  // Se nao estiver mais em estado critico, garante que o buzzer desligue
  if (status != "CRITICO") {
    digitalWrite(BUZZER_PIN, LOW);
    buzzerLigado = false;
  }
}

// ---------------------------------------------------------------------
// Faz o buzzer piscar (bipar) periodicamente enquanto o LED vermelho
// estiver aceso, sem usar delay() (nao bloqueante)
// ---------------------------------------------------------------------
void atualizarBuzzer(unsigned long agora) {
  bool emCritico = digitalRead(LED_VERMELHO) == HIGH;

  if (!emCritico) {
    return;
  }

  if (agora - ultimoToggleBuzzer >= INTERVALO_BUZZER) {
    ultimoToggleBuzzer = agora;
    buzzerLigado = !buzzerLigado;
    digitalWrite(BUZZER_PIN, buzzerLigado ? HIGH : LOW);
  }
}

// ---------------------------------------------------------------------
// Atualiza o LCD com temperatura, umidade e status
// ---------------------------------------------------------------------
void atualizarLCD(float temperatura, float umidade, String status) {
  lcd.setCursor(0, 0);
  lcd.print("T:");
  lcd.print(temperatura, 1);
  lcd.print("C U:");
  lcd.print((int)umidade);
  lcd.print("%  "); // espacos para limpar caracteres residuais

  lcd.setCursor(0, 1);
  lcd.print("Status: ");
  lcd.print(status);
  lcd.print("   "); // espacos para limpar caracteres residuais
}

// ---------------------------------------------------------------------
// Envia a leitura pela Serial no formato: temperatura,umidade,status
// ---------------------------------------------------------------------
void enviarSerial(float temperatura, float umidade, String status) {
  Serial.print(temperatura, 1);
  Serial.print(",");
  Serial.print((int)umidade);
  Serial.print(",");
  Serial.println(status);
}

// ---------------------------------------------------------------------
// Desliga LEDs e buzzer (usado na inicializacao)
// ---------------------------------------------------------------------
void desligarTudo() {
  digitalWrite(LED_AZUL, LOW);
  digitalWrite(LED_VERMELHO, LOW);
  digitalWrite(LED_BRANCO, LOW);
  digitalWrite(BUZZER_PIN, LOW);
}
