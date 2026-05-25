# Guía de Contribución

¡Gracias por tu interés en contribuir a Heimdall Ground Control!

## Cómo empezar

1. Haz un fork del repositorio
2. Clona tu fork: `git clone https://github.com/TU_USUARIO/xheimdall-ground-control.git`
3. Instala dependencias: `pnpm install`
4. Crea una rama: `git checkout -b feat/mi-feature`

## Flujo de trabajo

- Mantén commits pequeños y atómicos con mensajes descriptivos en español o inglés
- Ejecuta `pnpm exec tsc --noEmit` antes de cada commit para asegurar que TypeScript está limpio
- Ejecuta `pnpm build` para verificar que el build de producción funciona
- Abre un PR contra `main` con descripción clara del cambio

## Convenciones de código

- **TypeScript estricto** — sin `any`, sin `@ts-ignore` injustificado
- **Clean Architecture** — mantener la separación `types → schemas → api → stores → components`
- **Sin comentarios de código obvios** — solo documentar WHY cuando no es evidente
- **Imports absolutos** — usar `@/src/...` en lugar de rutas relativas

## Reporte de bugs

Abre un issue describiendo:
1. Comportamiento esperado vs. real
2. Pasos para reproducir
3. Versión del navegador y sistema operativo

## Licencia

Al contribuir aceptas que tu código se publique bajo la [licencia MIT](LICENSE).
