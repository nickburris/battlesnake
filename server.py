import os
import random
import copy

import cherrypy

"""
This is a simple Battlesnake server written in Python.
For instructions see https://github.com/BattlesnakeOfficial/starter-snake-python/README.md
"""

# TODO log to file
def log(m):
  print(m)

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
    head_x = -1
    head_y = -1
    tail_dir = None

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
      return self.unoccupied(dest_x, dest_y) or (m == self.tail_dir and not self.growing())

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
    
    def health_low(self):
      return self.data["you"]["health"] <= 50

    def growing(self):
      return self.just_ate

    def get_length(self):
      return self.data["you"]["length"]

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

      log(f"[breathing_room] Breathing room {room} in direction {m}")
      self.breathing_rooms[m] = room
      return room

    # Return whether there is an enemy with head at (x, y)
    def is_enemy_head(self, x, y):
      if not self.in_range(x, y):
        return False
      if x == self.head_x and y == self.head_y:
        return False
      return self.board[x][y] == "head"

    # Return the length of the snake with head at (x, y)
    def length_of_enemy(self, x, y):
      if not self.is_enemy_head(x, y):
        return -1
      
      # Search for the snake
      # TODO index snakes by head position
      for snake in self.data["board"]["snakes"]:
        if x == snake["head"]["x"] and y == snake["head"]["y"]:
          return snake["length"]
      return -1

    # Return whether the destination in direction m has a snake one
    # space away that could move there at the same time, and that snake
    # has higher health than us.
    def possible_losing_fight(self, m):
      dest_x, dest_y = self.get_dest(m)
      if not self.unoccupied(dest_x, dest_y):
        return False
      
      enemy_lengths = [
          self.length_of_enemy(dx,dy) for (dx,dy) in [(dest_x+1,dest_y),(dest_x,dest_y+1),(dest_x-1,dest_y),(dest_x,dest_y-1)]]
      for enemy_length in enemy_lengths:
        # TODO the enemy might be growing, so this is extra careful but
        # could actually track if the enemy is growing.
        if self.get_length() <= enemy_length + 1:
          log(f"[possible_losing_fight] Move {m} is a possible losing fight because of enemy with length {enemy_length}")
          return True
      return False
    
    # Return the direction(s) that move toward (x, y)
    def directions_toward(self, x, y):
      directions = []
      if x < self.head_x:
        directions.append("left")
      elif x > self.head_x:
        directions.append("right")
      if y < self.head_y:
        directions.append("down")
      elif y > self.head_y:
        directions.append("up")
      
      return directions

    # Return the direction(s) that move toward the nearest food
    # TODO this is absolute nearest, doesn't account for things in the way
    def nearest_food_directions(self):
      foods = [(food["x"], food["y"]) for food in self.data["board"]["food"]]
      foods.sort(key=lambda food: abs(food[0]-self.head_x) + abs(food[1]-self.head_y))
      (fx, fy) = foods[0]
      directions = self.directions_toward(fx, fy)
      log(f"[nearest_food_directions] return {directions}")
      return directions

    # Return whether we're the longest snake
    def am_longest(self):
      for snake in self.data["board"]["snakes"]:
        if snake["length"] > self.get_length():
          return False
      return True

    # Decide a move based on the game data
    def move(self, data):
        self.data = data
        self.make_board()
        self.breathing_rooms = {}
        self.head_x = data["you"]["head"]["x"]
        self.head_y = data["you"]["head"]["y"]
        self.tail_dir = self.find_tail()

        move = "up"

        possible_moves = ["up", "down", "left", "right"]
        possible_moves = [m for m in possible_moves if self.possible(m)]
        
        to_tail = self.tail_dir
        if to_tail and self.am_longest() and not self.growing() and not self.health_low() and not self.possible_losing_fight(to_tail):
          # TODO shouldn't always follow tail, e.g. if health is low
          log(f"[move] Moving {to_tail} (following tail)")
          return to_tail

        preferred_moves = copy.deepcopy(possible_moves)

        # Prefer moves that aren't a possible head-to-head in a losing battle
        log("[move] Checking for possible losing fights")
        preferred_moves = [
            m for m in preferred_moves if not self.possible_losing_fight(m)] or preferred_moves

        # Prefer to move in the direction with the most "breathing room"
        # TODO consider that a areas may open up "before it's too late",
        # i.e. if we're choosing between an area of 4 and an area of 6 but the 
        # area of 4 would expand to 20 before it's too late then we'd want to go
        # that way. Similarly, the area with the most breathing room might close
        # off.
        preferred_moves.sort(key=self.breathing_room, reverse=True)
        if preferred_moves:
          most_room = self.breathing_room(preferred_moves[0])
        preferred_moves = [
            m for m in preferred_moves if self.breathing_room(m) == most_room]

        # Prefer moves that move toward food
        log("[move] Checking for moves toward food")
        nearest_food_directions = self.nearest_food_directions()
        preferred_moves = [
            m for m in preferred_moves if m in nearest_food_directions] or preferred_moves

        # Choose a random direction to move in
        if preferred_moves:
          log(f"[move] Choosing from preferred moves {preferred_moves}")
          move = random.choice(preferred_moves)
        elif possible_moves:
          log(f"[move] No preferred moves, choosing possible move from {possible_moves}")
          move = random.choice(possible_moves)
        else:
          log("[move] No possible moves!")

        # Set whether we'll be growing next move
        self.just_ate = self.will_eat(move)

        log(f"[move] Moving {move}")
        return move

    def end(self, data):
        # TODO determine if we won
        log("[end] GG")

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
        log(f"Starting game {id}")
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
        log(f"Game {id}")
        return {"move": self.games[id].move(data)}

    @cherrypy.expose
    @cherrypy.tools.json_in()
    def end(self):
        # This function is called when a game your snake was in ends.
        # It's purely for informational purposes, you don't have to make any decisions here.
        data = cherrypy.request.json
        id = data["game"]["id"]
        log(f"Game {id} over")
        self.games[id].end(data)
        self.games[id] = None
        return "ok"


if __name__ == "__main__":
    server = Server()
    cherrypy.config.update({"server.socket_host": "0.0.0.0"})
    cherrypy.config.update(
        {"server.socket_port": int(os.environ.get("PORT", "8080")),}
    )
    log("Starting Battlesnake Server...")
    cherrypy.quickstart(server)
