"""game_documents / build_passages 리팩터링 회귀 테스트"""

import unittest

from backend import features, semantic

# 리팩터링 전 build_passages 출력 (첫 3행)
BASELINE_PASSAGES = ['passage: Die Macher. Mechanics: Alliances, Area Majority / Influence, Auction/Bidding, Dice Rolling, Hand Management, Simultaneous Action Selection, Negotiation. Themes: Economic, Political. Die Macher is a game about seven sequential political races in different regions of Germany. Players are in charge of national political parties, and must manage limited resources to help their party to victory. The winning party will have the most victory points after all the regional elections. There are four different ways of scoring victory points. First, each regional election can supply one to eighty victory points, depending on the size of the region and how well your party does in it. Second, if a party wins a regional election and has some media influence in the region, then the party will receive some media-control victory points. Third, each party has a national party membership which will grow as the game progresses and this will supply a fair number of victory points. Lastly, parties score some victory points if their party platform matches the national opinions at the end of the game.\n\nThe 1986 edition featured four parties from the old West Germany and supported 3-4 players. The 1997 edition supports up to five players in the re-united Germany and updated several features of the rules as well.  The 2006 edition also supports up to five players and adds a shorter five-round variant and additional rules updates by the original designer.', 'passage: Dragonmaster. Mechanics: Trick-taking. Themes: Fantasy. Dragonmaster is a trick-taking card game based on an older game called Coup d\'État. Each player is given a supply of plastic gems, which represent points. Each player will get to be the dealer for five different hands, with slightly different goals for each hand. After all cards have been dealt out, the dealer decides which hand best suits his or her current cards, and the other players are penalized points (in the form of crystals) for taking certain tricks or cards. For instance, if "first" or "last" is called, then a player is penalized for taking the first or last tricks. All players will get a chance to be dealer for five hands, but other players can steal this opportunity by taking all of the tricks during certain hands. At the end, the biggest pile of gems wins the game.\n\nJewel contents:\n\n10 clear (2 extra)\n14 green (2 extra)\n22 red (2 extra)\n22 blue (2 extra)', 'passage: Samurai. Mechanics: Area Majority / Influence, Hand Management, Hexagon Grid, Once-Per-Game Abilities, Set Collection, Tile Placement. Themes: Medieval, Theme_Samurai. Samurai is set in medieval Japan. Players compete to gain the favor of three factions: samurai, peasants, and priests, which are represented by helmet, rice paddy, and Buddha figures scattered about the board, which features the islands of Japan. The competition is waged through the use of hexagonal tiles, each of which help curry favor of one of the three factions — or all three at once! Players can make lightning-quick strikes with horseback ronin and ships or approach their conquests more methodically. As each figure (helmets, rice paddies, and Buddhas) is surrounded, it is awarded to the player who has gained the most favor with the corresponding group.\n\nGameplay continues until all the symbols of one type have been removed from the board or four figures have been removed from play due to a tie for influence.\n\nAt the end of the game, players compare captured symbols of each type, competing for majorities in each of the three types. Ties are not uncommon and are broken based on the number of other, "non-majority" symbols each player has collected.\n\nThe game is part of what is sometimes called the Knizia tile-laying trilogy.']


class SemanticDocumentsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = features.load_games().head(3)
        cls.mech = features.load_binary_features(features.MECHANICS_PATH, cls.df["BGGId"])
        cls.theme = features.load_binary_features(features.THEMES_PATH, cls.df["BGGId"])

    def test_build_passages_unchanged_and_documents_match(self):
        docs = semantic.game_documents(self.df, self.mech, self.theme)
        passages = semantic.build_passages(self.df, self.mech, self.theme)
        self.assertEqual(passages, BASELINE_PASSAGES)
        self.assertEqual(len(docs), 3)
        for (title, body), passage in zip(docs, passages):
            self.assertEqual(passage, f"passage: {title}. {body}")
        self.assertEqual(docs[0][0], self.df.iloc[0]["Name"])


if __name__ == "__main__":
    unittest.main()
