# Dato Express — Cómo se publica un video nuevo

Instrucciones para la tarea diaria. Sitio: https://datoexpress-web.vercel.app (Vercel publica solo cada push a `main`).

## Pasos

1. **Tendencias**: con vidIQ (`vidiq_instagram_tiktok_outlier_search` en español, audiencia Argentina/Latinoamérica, y `vidiq_trending_videos` con `videoFormat: short`, `videoTitleLanguage: es`) buscar qué curiosidades están funcionando esta semana.
2. **Elegir el tema** — sin repetir temas que ya estén en `videos.json`. Preferir formatos "3 datos de X que parecen mentira" o "¿Sabías que…?".
3. **Verificar cada dato** con al menos una búsqueda web y fuentes confiables. Si un dato no se confirma, cambiarlo. Nada de política, salud con consejos médicos, ni personas reales en tono negativo.
4. **Guion**: copiar `generador/guiones/guion_001.json` como `guion_NNN.json` (NNN = siguiente número), cambiar textos y `output` a `videos/dato-NNN.mp4`.
   - Escenas: `hook` (3 s) → 3 × `fact` (6–6.5 s) → `cta` (3.5 s). Total ~25 s.
   - `fact` usa `count_from`/`count_to` para un número animado, o `big` para un texto grande.
   - Palabras entre `*asteriscos*` salen en amarillo.
   - Estilo aprobado: ver `guion_002.json` (línea de tiempo `timeline`, barras `bars`, ilustraciones `art`).
   - **Ilustraciones**: dibujarlas como SVG plano (paleta amarilla/arena, fondo transparente) en `generador/art/NOMBRE.svg`, pasarlas a PNG con Playwright (`locator("svg").screenshot(omit_background=True)`) y usarlas en `art` con `anim: "float"`. `"img": "venus"` dibuja un planeta animado sin archivo.
   - **Voz** (opcional, 28 créditos de vidIQ por video): `vidiq_voiceover_generate` con la voz Francisco (`EK54is7sa3aPFLD9BwCC`) y `scriptLines` = una línea por escena. Poner en el guion `voice` (ruta del mp3) y `voice_lines` (start/dur que devuelve vidIQ), y ajustar cada `dur` de escena a duración de la línea + 0.5 s. Si el mp3 no se puede descargar (assets.vidiq.com bloqueado), hacer el video sin voz.
5. **Render**: desde la raíz del repo
   - vista previa: `python3 generador/make_video.py generador/guiones/guion_NNN.json /tmp/out --preview` y mirar los JPG (que nada se superponga ni se corte).
   - video: `python3 generador/make_video.py generador/guiones/guion_NNN.json /tmp/out`
   - miniatura: `ffmpeg -ss 1.8 -i videos/dato-NNN.mp4 -frames:v 1 -vf scale=540:960 -q:v 4 videos/dato-NNN.jpg`
6. **videos.json**: agregar la entrada nueva (id, fecha de hoy, titulo, descripcion, tema, video, miniatura).
7. **Publicar**: commit y push a `main`. Verificar en Vercel que el deploy quede `READY` y que el video cargue en el sitio.
8. **Instagram** (cuando la cuenta esté conectada en vidIQ): publicar el Reel con texto + hashtags (#datoscuriosos #curiosidades #sabiasque + 2 del tema).
