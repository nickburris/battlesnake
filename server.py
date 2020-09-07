import os
import random

import cherrypy

"""
This is a simple Battlesnake server written in Python.
For instructions see https://github.com/BattlesnakeOfficial/starter-snake-python/README.md
"""


class Battlesnake(object):
    # State set per-turn
    data = None
    board = None

    # State stored across turns
    # TODO this assumes one game at a time, move all logic to a different
    # class and create an instance per game ID
    just_ate = False

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        # This function is called when you register your Battlesnake on play.battlesnake.com
        # It controls your Battlesnake appearance and author permissions.
        # TIP: If you open your Battlesnake URL in browser you should see this data
        return {
            "apiversion": "1",
            "author": "nickburris",
            "color": "#fc6149",
            "head": "pixel",
            "tail": "hook",
        }

    @cherrypy.expose
    @cherrypy.tools.json_in()
    def start(self):
        # This function is called everytime your snake is entered into a game.
        # cherrypy.request.json contains information about the game that's about to be played.
        # TODO: Use this function to decide how your snake is going to look on the board.
        data = cherrypy.request.json

        # Initialize game state
        # TODO assumes one game at a time, should actually create a new
        # game instance.
        self.growing = False

        print("START")
        print(data)
        return "ok"

    def make_board(self):
      self.board = [[None for y in range(self.data["board"]["height"])]
          for x in range(self.data["board"]["width"])]
      
      for snake in self.data["board"]["snakes"]:
        for body in snake["body"]:
          self.board[body["x"]][body["y"]] = "body"
        self.board[snake["head"]["x"]][snake["head"]["y"]] = "head"

      for food in self.data["board"]["food"]:
        self.board[food["x"]][food["y"]] = "food"

    def get_dest(self, m):
      dest_x = self.data["you"]["head"]["x"]
      dest_y = self.data["you"]["head"]["y"]
      if m == "up":
        dest_y+=1;
      elif m == "down":
        dest_y-=1;
      elif m == "left":
        dest_x-=1;
      elif m == "right":
        dest_x+=1;
      
      return dest_x, dest_y
    
    def possible(self, m):
      dest_x, dest_y = self.get_dest(m)
      
      # Check bounds
      if (dest_x < 0 or dest_x >= self.data["board"]["width"] or
          dest_y < 0 or dest_y >= self.data["board"]["height"]):
        return False
      
      # Check immediate collision
      if self.board[dest_x][dest_y] in {"body", "head"}:
        return False
      
      return True

    def will_eat(self, m):
      dest_x, dest_y = self.get_dest(m)
      if self.board[dest_x][dest_y] == "food":
        return True
      return False

    # Return the immediate direction that the tail is in if it is one space
    # away (i.e. it can be followed, but make sure to also check for growth)
    def find_tail(self):
      if self.data["you"]["length"] <= 3:
        return None

      head_x = self.data["you"]["head"]["x"]
      head_y = self.data["you"]["head"]["y"]
      tail_x = self.data["you"]["body"][-1]["x"]
      tail_y = self.data["you"]["body"][-1]["y"]
      if head_x == tail_x:
        if tail_y == head_y + 1:
          return "up"
        if tail_y == head_y - 1:
          return "down"
      if head_y == tail_y:
        if tail_x == head_x + 1:
          return "right"
        if tail_x == head_x - 1:
          return "left"
      
      return None

    def health_critical(self):
      return self.data["you"]["health"] <= 20

    def growing(self):
      return self.just_ate

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def move(self):
        # This function is called on every turn of a game. It's how your snake decides where to move.
        # Valid moves are "up", "down", "left", or "right".
        self.data = cherrypy.request.json
        self.make_board()

        move = "up"

        possible_moves = ["up", "down", "left", "right"]
        possible_moves = [m for m in possible_moves if self.possible(m)]
        
        to_tail = self.find_tail()
        if to_tail and not self.growing() and not self.health_critical():
          # TODO shouldn't always follow tail, e.g. if health is low
          print(f"MOVE: {to_tail} (following tail)")
          return {"move": to_tail}

        # Constricted moves probably lead to death
        # TODO remove constricted moves, like turning toward a corner/cave
        # ... follow up TODO what if they're all constricted? Then
        # constricted moves might be necessary and some constricted moves
        # may not be killers (e.g. they open up before it's too late)

        # Choose a random possible direction to move in
        if possible_moves:
          move = random.choice(possible_moves)
        else:
          print("No possible moves!")

        # Set whether we'll be growing next move
        self.just_ate = self.will_eat(move)

        print(f"MOVE: {move}")
        return {"move": move}

    @cherrypy.expose
    @cherrypy.tools.json_in()
    def end(self):
        # This function is called when a game your snake was in ends.
        # It's purely for informational purposes, you don't have to make any decisions here.
        data = cherrypy.request.json

        print("END")
        return "ok"


if __name__ == "__main__":
    server = Battlesnake()
    cherrypy.config.update({"server.socket_host": "0.0.0.0"})
    cherrypy.config.update(
        {"server.socket_port": int(os.environ.get("PORT", "8080")),}
    )
    print("Starting Battlesnake Server...")
    cherrypy.quickstart(server)
