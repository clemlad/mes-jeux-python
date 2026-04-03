import pygame
import sys
import random
import math
import time

pygame.init()
largeur, hauteur = 1000, 600
fenetre = pygame.display.set_mode((largeur, hauteur))
pygame.display.set_caption("Pong")

blanc = (255, 255, 255)
noir = (0, 0, 0)
gris_clair = (180, 180, 180)

raquette1 = pygame.Rect(50, hauteur // 2 - 70, 10, 140)
raquette2 = pygame.Rect(largeur - 60, hauteur // 2 - 70, 10, 140)
balle = pygame.Rect(largeur // 2 - 15, hauteur // 2 - 15, 30, 30)

score1 = 0
score2 = 0

police = pygame.font.Font(None, 48)

vitesse_ia = 7
ia_active = True
jeu_en_cours = False
pause = False
mode_jeu = "classique"
temps_de_compte_a_rebours = 300
temps_restant = temps_de_compte_a_rebours

nom_joueur1 = "Joueur 1"
nom_joueur2 = "Joueur 2"

parametres_partie = {}


def saisir_nom(message, suivant):
    global nom_joueur1, nom_joueur2
    texte = ''
    while True:
        fenetre.fill(noir)
        prompt = police.render(message + texte + '|', True, blanc)
        fenetre.blit(prompt, (largeur // 2 - prompt.get_width() // 2, hauteur // 2))
        bouton_retour = bouton_texte("Retour", largeur - 200, hauteur - 80)
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    if suivant == 'joueur1':
                        nom_joueur1 = texte if texte.strip() != "" else "Anonyme"
                        if ia_active:
                            initialiser_partie()
                        else:
                            saisir_nom("Nom Joueur 2 : ", 'joueur2')
                        return
                    else:
                        nom_joueur2 = texte if texte.strip() != "" else "Anonyme"
                        initialiser_partie()
                        return
                elif event.key == pygame.K_BACKSPACE:
                    texte = texte[:-1]
                else:
                    if len(texte) < 12:
                        texte += event.unicode
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if bouton_retour.collidepoint(event.pos):
                    if suivant == 'joueur2':
                        saisir_nom("Nom Joueur 1 : ", 'joueur1')
                    else:
                        choisir_nombre_joueurs()
                    return


def bouton_texte(texte, x, y):
    surface = police.render(texte, True, noir)
    rect = pygame.Rect(x, y, surface.get_width() + 40, surface.get_height() + 20)
    pygame.draw.rect(fenetre, gris_clair, rect, border_radius=8)
    fenetre.blit(surface, (rect.x + 20, rect.y + 10))
    return rect


def choisir_nombre_joueurs():
    global ia_active
    while True:
        fenetre.fill(noir)
        titre = police.render("Nombre de joueurs ?", True, blanc)
        fenetre.blit(titre, (largeur // 2 - titre.get_width() // 2, hauteur // 2 - 100))
        bouton_1j = bouton_texte("1 Joueur", largeur // 2 - 200, hauteur // 2 - 30)
        bouton_2j = bouton_texte("2 Joueurs", largeur // 2 + 50, hauteur // 2 - 30)
        bouton_retour = bouton_texte("Retour", largeur - 200, hauteur - 80)
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if bouton_1j.collidepoint(event.pos):
                    ia_active = True
                    saisir_nom("Nom Joueur 1 : ", 'joueur1')
                    return
                elif bouton_2j.collidepoint(event.pos):
                    ia_active = False
                    saisir_nom("Nom Joueur 1 : ", 'joueur1')
                    return
                elif bouton_retour.collidepoint(event.pos):
                    menu_mode()
                    return


def menu_mode():
    global mode_jeu
    while True:
        fenetre.fill(noir)
        titre = police.render("Choisissez le mode de jeu", True, blanc)
        fenetre.blit(titre, (largeur // 2 - titre.get_width() // 2, hauteur // 2 - 150))
        bouton_classique = bouton_texte("Classique", largeur // 2 - 200, hauteur // 2 - 30)
        bouton_endurance = bouton_texte("Endurance", largeur // 2 + 50, hauteur // 2 - 30)
        bouton_quitter = bouton_texte("Quitter", largeur // 2 - 75, hauteur // 2 + 80)
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if bouton_classique.collidepoint(event.pos):
                    mode_jeu = "classique"
                    choisir_nombre_joueurs()
                    return
                elif bouton_endurance.collidepoint(event.pos):
                    mode_jeu = "endurance"
                    choisir_nombre_joueurs()
                    return
                elif bouton_quitter.collidepoint(event.pos):
                    pygame.quit()
                    sys.exit()


def compte_a_rebours():
    for i in range(3, 0, -1):
        fenetre.fill(noir)
        texte = police.render(str(i), True, blanc)
        fenetre.blit(texte, (largeur // 2 - texte.get_width() // 2, hauteur // 2))
        pygame.display.flip()
        pygame.time.delay(1000)
    fenetre.fill(noir)
    go = police.render("Go !", True, blanc)
    fenetre.blit(go, (largeur // 2 - go.get_width() // 2, hauteur // 2))
    pygame.display.flip()
    pygame.time.delay(700)


def initialiser_partie():
    global score1, score2, temps_restant, parametres_partie, raquette1, raquette2
    score1 = 0
    score2 = 0
    temps_restant = temps_de_compte_a_rebours
    raquette1.y = hauteur // 2 - 70
    raquette2.y = hauteur // 2 - 70
    parametres_partie = {
        'mode_jeu': mode_jeu,
        'ia_active': ia_active,
        'nom_joueur1': nom_joueur1,
        'nom_joueur2': nom_joueur2,
    }
    compte_a_rebours()
    relancer_balle()


def relancer_balle():
    global balle, vitesse_balle_x, vitesse_balle_y, jeu_en_cours
    balle = pygame.Rect(largeur // 2 - 15, hauteur // 2 - 15, 30, 30)
    vitesse_balle_x = random.choice([-6, -5, 5, 6])
    vitesse_balle_y = random.choice([-6, -5, 5, 6])
    jeu_en_cours = True


def augmenter_vitesse():
    global vitesse_balle_x, vitesse_balle_y
    vitesse_balle_x *= 1.10
    vitesse_balle_y *= 1.10
    vitesse_balle_x = math.copysign(min(abs(vitesse_balle_x), 10), vitesse_balle_x)
    vitesse_balle_y = math.copysign(min(abs(vitesse_balle_y), 10), vitesse_balle_y)


def ia_move():
    if vitesse_balle_x > 0:
        if raquette2.centery < balle.centery and raquette2.bottom < hauteur:
            raquette2.y += vitesse_ia
        elif raquette2.centery > balle.centery and raquette2.top > 0:
            raquette2.y -= vitesse_ia
    else:
        if raquette2.centery < hauteur // 2:
            raquette2.y += 4
        elif raquette2.centery > hauteur // 2:
            raquette2.y -= 4


def verifier_victoire():
    global jeu_en_cours
    if mode_jeu == "classique":
        if (score1 >= 11 or score2 >= 11) and abs(score1 - score2) >= 2:
            jeu_en_cours = False
            if score1 > score2:
                gagnant = nom_joueur1
                afficher_victoire(f"{gagnant} a gagné !")
            else:
                gagnant = nom_joueur2
                if not ia_active:
                    afficher_victoire(f"{gagnant} a gagné !")
                else:
                    afficher_victoire("Un robot t'a battu")
    elif mode_jeu == "endurance":
        if temps_restant <= 0:
            jeu_en_cours = False
            if score1 > score2:
                afficher_victoire(f"{nom_joueur1} a gagné !")
            elif score2 > score1:
                if ia_active:
                    afficher_victoire("Un robot t'a battu !")
                else:
                    afficher_victoire(f"{nom_joueur2} a gagné !")
            else:
                afficher_victoire("Égalité !")

def afficher_victoire(texte):
    while True:
        fenetre.fill(noir)
        vic = police.render(texte, True, blanc)
        fenetre.blit(vic, (largeur // 2 - vic.get_width() // 2, hauteur // 2 - 100))
        bouton_rejouer = bouton_texte("Rejouer", largeur // 2 - 150, hauteur // 2)
        bouton_menu = bouton_texte("Menu principal", largeur // 2 - 150, hauteur // 2 + 80)
        bouton_quitter = bouton_texte("Quitter", largeur // 2 - 150, hauteur // 2 + 160)
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if bouton_rejouer.collidepoint(event.pos):
                    restaurer_parametres()
                    initialiser_partie()
                    return
                elif bouton_menu.collidepoint(event.pos):
                    menu_mode()
                    return
                elif bouton_quitter.collidepoint(event.pos):
                    pygame.quit()
                    sys.exit()


def restaurer_parametres():
    global mode_jeu, ia_active, nom_joueur1, nom_joueur2
    mode_jeu = parametres_partie.get('mode_jeu', "classique")
    ia_active = parametres_partie.get('ia_active', True)
    nom_joueur1 = parametres_partie.get('nom_joueur1', "Joueur 1")
    nom_joueur2 = parametres_partie.get('nom_joueur2', "Joueur 2")


def menu_pause():
    global pause
    while pause:
        fenetre.fill(noir)
        titre = police.render("Jeu en pause", True, blanc)
        fenetre.blit(titre, (largeur // 2 - titre.get_width() // 2, hauteur // 2 - 200))
        bouton_reprendre = bouton_texte("Reprendre", largeur // 2 - 150, hauteur // 2 - 80)
        bouton_menu = bouton_texte("Menu principal", largeur // 2 - 150, hauteur // 2 + 10)
        bouton_quitter = bouton_texte("Quitter", largeur // 2 - 150, hauteur // 2 + 100)
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if bouton_reprendre.collidepoint(event.pos):
                    pause = False
                elif bouton_menu.collidepoint(event.pos):
                    pause = False
                    menu_mode()
                elif bouton_quitter.collidepoint(event.pos):
                    pygame.quit()
                    sys.exit()


clock = pygame.time.Clock()
menu_mode()

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_p:
                pause = not pause
                if pause:
                    menu_pause()

    if not jeu_en_cours:
        continue

    if mode_jeu == "endurance" and not pause:
        temps_restant -= 1 / 60
        if temps_restant <= 0:
            verifier_victoire()
            continue

    touches = pygame.key.get_pressed()
    if touches[pygame.K_z]:
        raquette1.y = max(0, raquette1.y - 12)
    if touches[pygame.K_s]:
        raquette1.y = min(hauteur - raquette1.height, raquette1.y + 12)

    if ia_active:
        ia_move()
    else:
        if touches[pygame.K_UP]:
            raquette2.y = max(0, raquette2.y - 12)
        if touches[pygame.K_DOWN]:
            raquette2.y = min(hauteur - raquette2.height, raquette2.y + 12)

    balle.x += int(vitesse_balle_x)
    balle.y += int(vitesse_balle_y)

    if balle.top <= 0 or balle.bottom >= hauteur:
        vitesse_balle_y = -vitesse_balle_y

    if balle.colliderect(raquette1):
        balle.left = raquette1.right
        vitesse_balle_x = abs(vitesse_balle_x)
        augmenter_vitesse()
    elif balle.colliderect(raquette2):
        balle.right = raquette2.left
        vitesse_balle_x = -abs(vitesse_balle_x)
        augmenter_vitesse()

    if balle.left <= 0:
        score2 += 1
        verifier_victoire()
        relancer_balle()
    elif balle.right >= largeur:
        score1 += 1
        verifier_victoire()
        relancer_balle()

    fenetre.fill(noir)
    pygame.draw.rect(fenetre, blanc, raquette1)
    pygame.draw.rect(fenetre, blanc, raquette2)
    pygame.draw.ellipse(fenetre, blanc, (largeur // 2 - 70, hauteur // 2 - 70, 140, 140), 1)
    pygame.draw.line(fenetre, blanc, (largeur // 2, 0), (largeur // 2, hauteur), 1)
    pygame.draw.rect(fenetre, blanc, balle)

    score_display = police.render(f"{score1} - {score2}", True, blanc)
    fenetre.blit(score_display, (largeur // 2 - score_display.get_width() // 2, 20))

    if mode_jeu == "endurance":
        temps_affiche = police.render(f"{int(temps_restant) // 60}:{int(temps_restant) % 60:02d}", True, blanc)
        fenetre.blit(temps_affiche, (largeur - temps_affiche.get_width() - 20, 20))

    pygame.display.flip()
    clock.tick(60)