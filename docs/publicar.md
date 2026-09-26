# Publicar FastTack en internet desde tu Mac (Cloudflare)

FastTack sigue funcionando en tu Mac, con tus datos y tu Claude Code. Un **túnel de Cloudflare** le da una
dirección web (p. ej. `https://fasttack.tudominio.com`) sin abrir puertos del router, y **Cloudflare
Access** solo deja entrar a los correos que tú digas: al entrar, Cloudflare manda un código al correo.

Todo es gratis salvo el dominio (unos 10 € al año). Funciona mientras el Mac esté encendido con
FastTack en marcha.

## 1. Cuenta y dominio (una vez)

1. Crea una cuenta gratuita en <https://dash.cloudflare.com/sign-up>.
2. Necesitas un dominio gestionado por Cloudflare:
   - Si no tienes: en el panel, *Registrar dominios* (Domain Registration) → compra uno (p. ej. `nombredelequipo.es` o `.com`).
   - Si ya tienes uno en otro sitio: *Añadir un dominio* y cambia sus servidores DNS a los que te indique Cloudflare (tarda desde minutos a unas horas).

## 2. Instalar `cloudflared` en el Mac (una vez)

Abre el Terminal y pega la línea que corresponda a tu Mac ( → *Acerca de este Mac*: «Apple M…» = Apple Silicon; «Intel» = Intel):

```bash
# Apple Silicon (M1, M2, M3…)
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64.tgz | tar xz && sudo mv cloudflared /usr/local/bin/

# Intel
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz | tar xz && sudo mv cloudflared /usr/local/bin/
```

(Pide la contraseña del Mac.) Si tienes Homebrew, también vale `brew install cloudflared`.
Comprueba con `cloudflared --version`.

## 3. Crear el túnel (una vez)

```bash
cloudflared tunnel login
```
Se abre el navegador: entra en tu cuenta de Cloudflare y elige tu dominio. Luego:

```bash
cloudflared tunnel create fasttack
cloudflared tunnel route dns fasttack fasttack.tudominio.com
```
(cambia `tudominio.com` por el tuyo). La primera línea crea el túnel y guarda su credencial en
`~/.cloudflared/`; la segunda apunta `fasttack.tudominio.com` al túnel.

## 4. Restringir el acceso por correo (una vez) — imprescindible

Sin este paso, cualquiera con la dirección entraría.

1. En el panel de Cloudflare, abre **Zero Trust** (la primera vez pide un nombre de equipo y elegir el plan **Free**; puede pedir una tarjeta aunque no cobra).
2. **Access → Applications → Add an application → Self-hosted**.
3. *Application name*: FastTack. *Session duration*: 1 month (para no pedir el código cada día).
4. *Public hostname*: subdominio `fasttack`, dominio `tudominio.com`.
5. Crea una **policy**: *Action* = **Allow**; en *Include* elige **Emails** y escribe los correos del equipo (el tuyo, la tripulación, el entrenador).
6. En *Login methods*, deja **One-time PIN** (código por correo). Guarda.

Para dar o quitar acceso más adelante, edita esa lista de correos.

## 5. Arrancar FastTack con el túnel (cada vez)

En la carpeta de FastTack:

```bash
uv run fasttack --tunel --direccion https://fasttack.tudominio.com
```

FastTack solo escucha en el propio Mac y el túnel lo publica a través de Cloudflare (con el control de
acceso). Para pararlo todo: `Ctrl+C`.

**Que el Mac no se duerma**: *Ajustes del Sistema → Batería* (o *Pantalla*/*Ahorro de energía* en un
Mac de sobremesa) → evitar el reposo automático con el adaptador de corriente. O arranca así, que
evita el reposo mientras FastTack esté en marcha:

```bash
caffeinate -s uv run fasttack --tunel --direccion https://fasttack.tudominio.com
```

## 6. En el móvil

Abre `https://fasttack.tudominio.com`, pon tu correo, copia el código que llega y listo. En Safari,
*Compartir → Añadir a pantalla de inicio* para tenerla como una app. Cada navegador guarda su propio
barco de referencia: si el entrenador mira otro barco, no se lo cambia al resto.

## Prueba rápida sin dominio (solo para probar)

```bash
uv run fasttack --solo-este-ordenador        # en una ventana
cloudflared tunnel --url http://localhost:8000   # en otra
```

Imprime una dirección `https://….trycloudflare.com` que funciona al momento, **pero sin control de
acceso** y cambia cada vez: no la compartas; úsala solo para ver que todo va.

## Qué tener en cuenta

- **Datos**: todo sigue en tu Mac (carpeta `datos/`, incluidos los `.vkx`). Cloudflare solo hace de puerta.
- **Debrief con IA**: lo genera Claude Code en tu Mac con tu cuenta, como ahora. Se genera en segundo plano (tarda 30–100 s) y la página espera sola.
- **Varios a la vez**: pueden usarlo varios miembros del equipo al mismo tiempo. Cargar un campeonato nuevo tarda lo mismo que en local.
- **Si no carga**: comprueba que el Mac está encendido y FastTack en marcha; el registro del túnel está en `~/.cloudflared/fasttack.log`.
