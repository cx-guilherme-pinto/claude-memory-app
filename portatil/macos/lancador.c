/*
 * Lançador compilado da Memória portátil (macOS). Só é usado na versão assinada
 * (scripts/sign-macos.sh); o build normal usa o script portatil/macos/memoria.
 *
 * Faz o mesmo que o script: corre
 *   Contents/Resources/python/bin/python3 -I -B -m memoria <argumentos>
 * A notarização e o Gatekeeper esperam código Mach-O em Contents/MacOS: a
 * assinatura de um script fica em atributos estendidos, que se perdem facilmente.
 */
#include <errno.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char *argv[]) {
    char caminho[PATH_MAX], real[PATH_MAX], python[PATH_MAX];
    uint32_t tamanho = sizeof(caminho);
    if (_NSGetExecutablePath(caminho, &tamanho) != 0 || realpath(caminho, real) == NULL) {
        fprintf(stderr, "memoria: não encontrei o caminho do lançador.\n");
        return 1;
    }
    char *barra = strrchr(real, '/'); /* .../Contents/MacOS/memoria */
    if (barra == NULL) return 1;
    *barra = '\0';
    if (snprintf(python, sizeof(python), "%s/../Resources/python/bin/python3", real) >= (int)sizeof(python)) return 1;

    char **args = calloc((size_t)argc + 5, sizeof(char *));
    if (args == NULL) return 1;
    int n = 0;
    args[n++] = python;
    args[n++] = "-I"; /* ignora PYTHONPATH e afins do utilizador */
    args[n++] = "-B"; /* não escreve .pyc dentro da app (estragaria a assinatura) */
    args[n++] = "-m";
    args[n++] = "memoria";
    for (int i = 1; i < argc; i++) {
        if (strncmp(argv[i], "-psn_", 5) == 0) continue; /* argumento antigo do Finder */
        args[n++] = argv[i];
    }
    args[n] = NULL;
    execv(python, args);
    fprintf(stderr, "memoria: não consegui correr %s: %s\n", python, strerror(errno));
    return 1;
}
