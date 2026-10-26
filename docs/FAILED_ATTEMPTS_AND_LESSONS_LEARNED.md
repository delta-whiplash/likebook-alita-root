# Matrice des Échecs, Pièges & Retours d'Expérience (Failed Attempts & Dead Ends)

Ce document répertorie **toutes les impasses, tentatives infructueuses et pièges techniques** rencontrés lors de la recherche de root sur la **Boyue Likebook Alita (K103 / RK3368)**.

L'objectif est d'éviter à quiconque de perdre des dizaines d'heures à reproduire les mêmes erreurs en expliquant concrètement :
> **"Si tu fais X ➔ Il se passe Y ➔ Voici pourquoi techniquement."**

---

## Synthèse Rapide : Tableau Comparatif

| Action testée | Résultat observé | Cause technique sous le capot |
| :--- | :--- | :--- |
| **`fastboot oem unlock`** | ❌ Wipe complet des données (`userdata`) ou `device is locked` | Routine interne du bootloader Boyue qui force l'effacement de l'eMMC pour des raisons de sécurité fabricant. |
| **Magisk standard (v25 à v30)** | ❌ Écran noir / Bootloop / Rejet U-Boot | 1. Hash SHA-1 AOSP (8 champs) rejeté par le U-Boot Rockchip (qui attend 11 champs).<br>2. `magiskinit` crashe sur l'architecture hybride 32/64 bits du RK3368. |
| **Patch `default.prop` (4 lignes)** | ❌ Bootloop / Drop en Recovery | Perte du lien symbolique `default.prop -> system/etc/prop.default` emportant `ro.zygote=zygote64_32` ➔ Watchdog Zygote panique. |
| **Repack du ramdisk avec `find . \| cpio`** | ❌ Échec au boot / Crash `init` | `cpio` standard ajoute des préfixes `./` et altère les permissions des symlinks (mode 0777 au lieu de 0750) ➔ Rejeté par `init`. |
| **SELinux : bypasser `selinux_initialize(0)`** | ❌ Crash Kernel / Drop Recovery | Saute le chargement des règles. `selinux_android_restorecon("/init")` renvoie `-1` ➔ Déclenche un `PLOG(FATAL)` immédiat. |
| **SELinux : forcer `selinux_set_enforce(0)`** | ❌ Crash Kernel / Drop Recovery | L'écriture de `0` dans `/sys/fs/selinux/enforce` échoue avec `-EINVAL`/`-EPERM` ➔ Branchement fatal `cbnz w0, 0x40dcdc` ("Failed to set enforce mode"). |
| **SetUID `su` dans `/data/local/tmp`** | ❌ `EPERM` / Refus d'élévation | La partition `/data` est montée avec le flag **`nosuid`** dans `init.rockchip.rc`. Le noyau Linux ignore le bit SUID. |
| **Écriture directe sur `/system`** | ❌ `Read-only file system` | Partition `/system` protégée au niveau bloc par **dm-verity** (`/dev/block/dm-0`). |
| **APKs de root 1-clic (KingRoot, etc.)** | ❌ Échec / Crash de l'app | Failles de sécurité obsolètes (Kernel 3.x) corrigées sur le Kernel 4.4.103 d'Android 8.1. |
| **Passage de `ro.boot.verifiedbootstate` à `orange`** | ⚠️ Pop-up "Problème interne lié à votre appareil" au boot | Vérification VINTF Treble d'Android 8.1. Le kernel Boyue n'a pas `/proc/config.gz` (`CONFIG_IKCONFIG_PROC`), déclenchant `Missing config CONFIG_ANDROID`. |
| **La Voie Royale (Notre solution)** | ✅ **Root persistant, SELinux Permissive, 0 wipe, boot 16s** | **Patch `0x14000006` (`b 0x40d148`) dans `init`, `su` ARM64 freestanding dans `/sbin` (rootfs non-nosuid), signature SHA-1 Rockchip 11-champs.** |

---

## 1. Le Piège de l'Unlock : `fastboot oem unlock`

### Ce que l'on a testé
Tenter de déverrouiller le bootloader de manière classique via Fastboot :
```bash
adb reboot bootloader
fastboot oem unlock
# ou fastboot flashing unlock
```

### Ce qui s'est passé
* En fastboot standard, la commande échoue souvent avec `remote: 'device is locked'`.
* Si la commande finit par passer ou si un firmware effectue l'unlock, le bootloader exécute immédiatement un formatage bas niveau de la partition `userdata` (secteur 7 955 456).

### Pourquoi techniquement
Sur les liseuses Boyue, les partitions de données ne sont pas chiffrées par défaut, mais le bootloader intègre une routine matérielle de sécurité : tout changement d'état du verrouillage déclenche un `erase` automatique du secteur de début de `userdata`. 
**Règle d'or :** Il ne faut **JAMAIS** exécuter `oem unlock`. On utilise à la place le mode **Rockchip Miniloader** (`2207:330a`) qui permet de lire et flasher les secteurs eMMC sans jamais toucher au verrouillage OEM.

---

## 2. L'Échec de Magisk Standard (v25, v26, v27, v30)

### Ce que l'on a testé
Patcher `boot.img` avec l'application Magisk ou via l'utilitaire `magiskboot patch`.

### Ce qui s'est passé
* L'appareil refuse de démarrer, boucle sur le logo Likebook ou retombe immédiatement en Recovery Android.

### Pourquoi techniquement
Il y a deux causes distinctes :

#### Cause A : La signature propriétaire Rockchip U-Boot (11 champs vs 8 champs)
* Le format boot.img AOSP calcule un condensat SHA-1 sur 8 champs :
  $$\text{SHA-1}(kernel + kernel\_sz + ramdisk + ramdisk\_sz + second + second\_sz)$$
* Le U-Boot de Rockchip (`rk3368` / `rk30board`) exige un SHA-1 sur **11 champs** :
  $$\text{SHA-1}(kernel + k\_sz + ramdisk + r\_sz + second + s\_sz + tags\_addr + page\_sz + unused + name + cmdline)$$
* Si ce hash n'est pas écrit à l'offset `0x240` (`id[8]`), U-Boot refuse d'exécuter le noyau et saute directement dans la partition `recovery`.

#### Cause B : Incompatibilité de `magiskinit`
Magisk remplace le binaire `/init` de la racine par son propre binaire `magiskinit`. Sur le RK3368 avec un noyau aarch64 64-bit et un userspace 32/64-bit hybride Android 8.1, `magiskinit` échoue lors de la création du montage tmpfs racine avant le lancement de Zygote, entraînant un blocage complet du watchdog d'initialisation.

---

## 3. Les Pièges de SELinux dans le Binaire `/init`

Le noyau de la liseuse démarre nativement avec `androidboot.selinux=permissive` dans sa ligne de commande (`/proc/cmdline`). Cependant, au milieu du boot, l'utilitaire userspace `/init` force SELinux en mode `Enforcing`.

Voici le code désassemblé de la fonction critique dans `/init` (offset `0xd128`) :
```armasm
0x40d128:  orr     w0, wzr, #1           ; w0 = 1 (mode enforcing)
0x40d12c:  bl      0x45ee2c              ; appel à selinux_set_enforce(1)
0x40d130:  cbnz    w0, 0x40dcdc          ; SI échec (!= 0) -> panique FATAL
0x40d134:  bl      0x45d0c4              ; vérification selinux_is_enforcing()
0x40d138:  cmp     w0, #1
0x40d13c:  b.eq    0x40d148              ; si ok, saute à la suite
0x40d140:  orr     w0, wzr, #1
0x40d144:  bl      0x45ee2c              ; 2ème tentative selinux_set_enforce(1)
0x40d148:  ... suite de l'initialisation ...
```

### Tentative 1 : Sauter `selinux_initialize(0)`
* **Ce qu'on a fait :** Noper l'appel à `selinux_initialize` pour désactiver complètement SELinux dès le début.
* **Résultat :** Drop immédiat en Recovery.
* **Pourquoi :** `selinux_initialize` ne fait pas qu'activer SELinux, il charge la politique (`/sepolicy` ou `/vendor/etc/selinux/precompiled_sepolicy`). Quelques instructions plus loin, `init` appelle `selinux_android_restorecon("/init")`. Comme aucune politique n'est chargée, cette fonction retourne `-1`, provoquant un crash fatal : `PLOG(FATAL) << "restorecon failed"`.

### Tentative 2 : Remplacer `selinux_set_enforce(1)` par `selinux_set_enforce(0)`
* **Ce qu'on a fait :** Modifier l'argument `w0` à `0x40d128` pour forcer la valeur `0` au lieu de `1`.
* **Résultat :** Drop immédiat en Recovery.
* **Pourquoi :** La fonction `selinux_set_enforce(0)` tente d'écrire `"0"` dans `/sys/fs/selinux/enforce`. À cet instant du démarrage sous Android 8.1, le pseudo-système de fichiers SELinux refuse cette écriture (`-EINVAL` ou `-EPERM`). La fonction renvoie donc `-1`. L'instruction à `0x40d130` (`cbnz w0, 0x40dcdc`) teste si `w0 != 0` ; comme `w0 = -1`, elle saute directement dans `PLOG(FATAL) << "Failed to set enforce mode"`.

### ✅ La Solution Gagnante : Le Saut Inconditionnel
* **Ce qu'on a fait :** Remplacer l'instruction à l'offset `0xd130` (`cbnz w0, 0x40dcdc`) par :
  ```armasm
  b 0x40d148    ; opcode ARM64: 0x14000006 (little-endian: 06 00 00 14)
  ```
* **Résultat :** Succès total ! Le système saute par-dessus la vérification d'erreur et par-dessus le second appel `selinux_set_enforce(1)`. Le noyau reste dans son mode initial (`Permissive`), la politique SELinux reste chargée, et aucun crash ne se produit.

---

## 4. Les Pièges du Ramdisk et du Système de Fichiers

### Tentative : Remplacer `default.prop` par un fichier personnalisé
* **Ce qu'on a fait :** Créer un fichier `default.prop` avec `ro.secure=0` et `ro.debuggable=1`.
* **Résultat :** Bootloop complet, Zygote ne démarre jamais.
* **Pourquoi :** Sur Android 8.1, `default.prop` à la racine est un **symlink** pointant vers `system/etc/prop.default`. Si on remplace ce lien par un fichier court, Android perd des dizaines de propriétés critiques, notamment `ro.zygote=zygote64_32`. Sans cette variable, `init` ne sait pas quel binaire Zygote instancier et le système s'arrête.
* **Règle :** Toujours préserver le symlink `default.prop -> system/etc/prop.default`.

### Tentative : Repack CPIO classique via ligne de commande Linux
* **Ce qu'on a fait :** `find . | cpio -o -H newc | gzip > ramdisk.cpio`.
* **Résultat :** Bootloop.
* **Pourquoi :** La commande `find` insère `./` devant chaque nom de fichier (`./init`, `./sbin`). De plus, les permissions des liens symboliques sont converties en `0777` par défaut par le cpio hôte. Le parser d'Android `init` rejette les chemins contenant `./` pour les exécutables initiaux.
* **Règle :** Utiliser exclusivement `magiskboot cpio ramdisk.cpio "<commande>"` pour toute modification in-place du ramdisk, ce qui garantit la préservation exacte des modes octaux et des structures CPIO Android.

---

## 5. Les Pièges du SetUID et du Binaire `su`

### Tentative : Poser un binaire `su` SetUID dans `/data/local/tmp`
* **Ce qu'on a fait :** `cp su /data/local/tmp/su && chmod 4755 /data/local/tmp/su`.
* **Résultat :** Exécuté par un utilisateur non-root, le binaire renvoie `EPERM` ou reste avec `uid=2000`.
* **Pourquoi :** Dans `init.rockchip.rc`, la partition `/data` est explicitement montée avec :
  ```text
  mount dummy dummy /data remount nosuid nodev noatime
  ```
  L'option noyau Linux `nosuid` neutralise entièrement le bit SetUID sur tous les fichiers résidant sur `/data`.

### ✅ La Solution Gagnante : L'installation dans `/sbin` (Rootfs)
* **Pourquoi `/sbin` fonctionne :**
  1. `/sbin` réside directement dans le `rootfs` (RAMDisk monté sur `/`).
  2. Le montage de `rootfs` est : `rootfs on / type rootfs (rw,seclabel)` ➔ **PAS de flag `nosuid`** !
  3. La variable d'environnement `$PATH` système déclarée dans `/init.rockchip.rc` commence par `/sbin` :
     ```text
     export PATH /sbin:/vendor/bin:/system/sbin:/system/bin:/system/xbin
     ```
  4. En intégrant un binaire `su` autonome (freestanding ARM64, sans glibc) en mode `04755` directement dans le ramdisk au niveau de `/sbin/su`, n'importe quel processus peut appeler `su` et devenir instantanément `uid=0` sans dépendre d'aucun daemon réseau ni socket IPC.

---

## 6. Le Mystère de la Pop-up Treble VINTF

### Ce qui s'est passé
Après un boot où `ro.boot.verifiedbootstate` a été forcé à `orange` via `resetprop`, une boîte de dialogue est apparue à l'écran :
> *"Un problème interne lié à votre appareil est survenu. Veuillez contacter le fabricant pour en savoir plus."*

### Pourquoi techniquement
Dans les sources d'Android 8.1 AOSP (`ActivityManagerService.java`), le système exécute au démarrage :
```java
if (!Build.isBuildConsistent()) {
    Slog.e(TAG, "Build fingerprint is not consistent, warning user");
    showInternalErrorDialog();
}
```
Dans `Build.java`, la méthode `isBuildConsistent()` appelle le validateur Treble :
```java
int result = VintfObject.verify(packageInfo);
```
Dans les journaux logcat :
```text
VintfObject.verify() returns 1: Runtime info and framework compatibility matrix are incompatible: Missing config CONFIG_ANDROID
```
* **Explication :** `/system/compatibility_matrix.xml` exige que le noyau fournisse sa configuration via `/proc/config.gz`. Le noyau 4.4.103 de Boyue a été compilé sans l'option `CONFIG_IKCONFIG_PROC=y`. Le validateur ne trouvant aucune option, il déclare le noyau "incompatible" et affiche cet avertissement.
* **Impact :** Purement visuel. L'application de lecture et le système fonctionnent à 100 %.
* **Solution :** Soit laisser `ro.boot.verifiedbootstate` sur `green`, soit fermer automatiquement la boîte de dialogue en 1 seconde via un sous-shell dans `boot_root.sh` (`input tap 1137 1045`).
