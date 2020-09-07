import os
import random
import copy

import cherrypy

"""
This is a simple Battlesnake server written in Python.
For instructions see https://github.com/BattlesnakeOfficial/starter-snake-python/README.md
"""

def in_board_range(board, x, y):
  if (x < 0 or x >= len(board) or
      y < 0 or y >= len(board[0])):
    return False
  return True

def board_space_unoccupied(board, x, y):
  if not in_board_range(board, x, y):
    return False
  
  # Check immediate collision
  if board[x][y] in {"body", "head"}:
    return False

  return True

class Battlesnake(object):
    # State set per-turn
    data = None
    board = None
    breathing_rooms = {}

    # State stored across turns
    just_ate = False

    def __init__(self):
      self.just_ate = False

    def make_board(self):
      self.board = [["space" for y in range(self.data["board"]["height"])]
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

    def in_range(self, x, y):
      return in_board_range(self.board, x, y)

    def unoccupied(self, x, y):
      return board_space_unoccupied(self.board, x, y)

    def possible(self, m):
      dest_x, dest_y = self.get_dest(m)
      return self.unoccupied(dest_x, dest_y)

    def will_eat(self, m):
      dest_x, dest_y = self.get_dest(m)

      if not self.in_range(dest_x, dest_y):
        return False

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

    # Returns the area of the shape including the space in direction m
    def breathing_room(self, m):
      if m in self.breathing_rooms:
        return self.breathing_rooms[m]

      dest_x, dest_y = self.get_dest(m)
      # Dest is expected to be unoccupied
      if not self.unoccupied(dest_x, dest_y):
        return 0

      board = copy.deepcopy(self.board)
      room = 0
      queue = []
      queue.append((dest_x, dest_y))
      while queue:
        (x, y) = queue.pop(0)
        if not board_space_unoccupied(board, x, y):
          continue
        if board[x][y] == "mark":
          continue
        room += 1
        board[x][y] = "mark"

        moves = [
          (dx,dy) for (dx,dy) in [(x+1,y),(x,y+1),(x-1,y),(x,y-1)] if self.in_range(dx, dy)]
        for (dx, dy) in moves:
          if board_space_unoccupied(board, dx, dy):
            queue.append((dx, dy))

      self.breathing_rooms[m] = room
      return room

    def move(self, data):
        self.data = data
        self.make_board()
        self.breathing_rooms = {}

        move = "up"

        possible_moves = ["up", "down", "left", "right"]
        possible_moves = [m for m in possible_moves if self.possible(m)]
        
        to_tail = self.find_tail()
        if to_tail and not self.growing() and not self.health_critical():
          # TODO shouldn't always follow tail, e.g. if health is low
          print(f"MOVE: {to_tail} (following tail)")
          return {"move": to_tail}

        # Prefer to move in the direction with the most "breathing room"
        # TODO consider that a areas may open up "before it's too late",
        # i.e. if we're choosing between an area of 4 and an area of 6 but the 
        # area of 4 would expand to 20 before it's too late then we'd want to go
        # that way. Similarly, the area with the most breathing room might close
        # off.
        possible_moves.sort(key=self.breathing_room, reverse=True)
        if possible_moves:
          most_room = self.breathing_room(possible_moves[0])
        preferred_moves = [
            m for m in possible_moves if self.breathing_room(m) == most_room]

        # Choose a random direction to move in
        if preferred_moves:
          move = random.choice(preferred_moves)
        elif possible_moves:
          move = random.choice(possible_moves)
        else:
          print("No possible moves!")

        # Set whether we'll be growing next move
        self.just_ate = self.will_eat(move)

        print(f"Move {move}")
        return move

    def end(self, data):
        # TODO determine if we won
        print("GG")

class Server(object):
    games = {}

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
        data = cherrypy.request.json
        id = data["game"]["id"]
        print(f"Starting game {id}")
        self.games[id] = Battlesnake()
        return "ok"

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def move(self):
        # This function is called on every turn of a game. It's how your snake decides where to move.
        # Valid moves are "up", "down", "left", or "right".
        data = cherrypy.request.json
        id = data["game"]["id"]
        print(f"Game {id}")
        return {"move": self.games[id].move(data)}

    @cherrypy.expose
    @cherrypy.tools.json_in()
    def end(self):
        # This function is called when a game your snake was in ends.
        # It's purely for informational purposes, you don't have to make any decisions here.
        data = cherrypy.request.json
        id = data["game"]["id"]
        print(f"Game {id} over")
        self.games[id].end(data)
        self.games[id] = None
        return "ok"


if __name__ == "__main__":
    server = Server()
    cherrypy.config.update({"server.socket_host": "0.0.0.0"})
    cherrypy.config.update(
        {"server.socket_port": int(os.environ.get("PORT", "8080")),}
    )
    print("Starting Battlesnake Server...")
    cherrypy.quickstart(server)
