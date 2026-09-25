# Simple Chat – interný chat pre Home Assistant

Vlastná HACS integrácia + Lovelace karta, ktorá zabezpečí chat medzi všetkými
užívateľmi tvojej HA inštancie (napr. ty a partnerka). Správy sa posielajú
cez WebSocket v reálnom čase a ukladajú sa perzistentne do `.storage`.

## Funkcie
- Real-time doručovanie správ cez HA WebSocket API (bez pollovania)
- Perzistentná história (`.storage/simple_chat.messages`), max 1000 správ
- Avatar + farba priradená každému userovi (odvodená z user ID)
- Oddeľovače dní, časové značky
- Príznaky prečítania (✓ odoslané / ✓✓ videné)
- Indikátor písania ("píše…")
- Emoji reakcie na správy
- Mazanie vlastných správ (admin môže mazať všetky)
- Badge s počtom neprečítaných správ v hlavičke karty
- Dizajn zladený s tvojím dashboardom (`#1a1f2e → #1e2438` gradient, `#60a5fa` accent, 16px radius)

## Inštalácia

### 1. Backend integrácia
1. Skopíruj priečinok `custom_components/simple_chat` do `<config>/custom_components/`
   (buď manuálne, alebo pridaj tento repozitár do HACS ako Custom repository → Integration).
2. Reštartuj Home Assistant.
3. Choď do **Nastavenia → Zariadenia a služby → Pridať integráciu** a vyhľadaj
   **Simple Chat**. Stačí potvrdiť, žiadne parametre netreba.

### 2. Frontend karta
Integrácia sa pokúsi zaregistrovať `simple-chat-card.js` automaticky pri štarte
(`/simple_chat_frontend/simple-chat-card.js`). Ak sa karta v editore dashboardu
neobjaví, pridaj ju ručne:

**Nastavenia → Dashboardy → Zdroje (Resources) → Pridať zdroj**
- URL: `/simple_chat_frontend/simple-chat-card.js`
- Typ: JavaScript Module

### 3. Pridanie na dashboard
```yaml
type: custom:simple-chat-card
title: Chat
height: 480
```

## Poznámky k implementácii
- Testované koncepčne proti aktuálnemu HA Core WebSocket API a `Store` helperu;
  keďže `async_register_static_paths` / `StaticPathConfig` sa medzi verziami HA
  mierne menili, over si po inštalácii logy – kód má fallback na staršie API,
  ale ak používaš veľmi starú alebo veľmi novú verziu, možno bude treba
  `__init__.py` mierne doladiť.
- Autentifikácia a identita usera sa berie priamo z HA session (`connection.user`),
  takže žiadne vlastné prihlasovanie netreba – každý user vidí chat pod svojím
  HA účtom.
- Mazanie: bežný user môže zmazať iba svoje správy, admin účet môže zmazať
  ktorúkoľvek.
- Ak chceš notifikácie (napr. mobilná appka) pri novej správe, najjednoduchšie
  je pridať automáciu, ktorá počúva event `simple_chat_new_message` a posiela
  `notify.mobile_app_...` – v evente je `user_name` a `text`.
