import numpy as np
import random

import torch
import torch.nn.functional as F
import torch.optim as optim

from collections import deque

from dqn import QNetwork
from dqn import ReplayBuffer

class Agent():
    """Basic experinece replay agent."""

    def __init__(self, state_size, action_size, seed, buffer_size=int(1e5), 
                 batch_size=64, gamma=0.99, tau=1e-3, lr=5e-4, update_every=4, checkpoint_file='checkpoint.pth'):
        """Initialize an Agent object.
        
        Params
        ======
            state_size (int): dimension of each state
            action_size (int): dimension of each action
            seed (int): random seed
            buffer_size(int):  replay buffer size
            batch_size(int):   minibatch size
            gamma:             discount factor
            tau:               for soft update of target parameters
            lr:                learning rate 
            update_every:      how often to update the network
            
        """
        self.state_size = state_size
        self.action_size = action_size
        self.seed = random.seed(seed)
        self.buffer_size = buffer_size
        self.batch_size = batch_size
        self.gamma = gamma
        self.tau = tau
        self.lr = lr
        self.update_every = update_every
        self.checkpoint_file = checkpoint_file
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        

        # Q-Network
        self.qnetwork_local = QNetwork(state_size, action_size, seed).to(self.device)
        self.qnetwork_target = QNetwork(state_size, action_size, seed).to(self.device)
        self.optimizer = optim.Adam(self.qnetwork_local.parameters(), lr=lr)

        # Replay memory
        self.memory = ReplayBuffer(action_size, buffer_size, batch_size, seed, self.device)
        # Initialize time step (for updating every UPDATE_EVERY steps)
        self.t_step = 0
    
    def step(self, state, action, reward, next_state, done):
        # Save experience in replay memory
        self.memory.add(state, action, reward, next_state, done)
        
        # Learn every UPDATE_EVERY time steps.
        self.t_step = (self.t_step + 1) % self.update_every
        if self.t_step == 0:
            # If enough samples are available in memory, get random subset and learn
            if len(self.memory) > self.batch_size:
                experiences = self.memory.sample()
                self.learn(experiences, self.gamma)

    def act(self, state, eps=0.):
        """Returns actions for given state as per current policy.
        
        Params
        ======
            state (array_like): current state
            eps (float): epsilon, for epsilon-greedy action selection
        """
        state = torch.from_numpy(state).float().unsqueeze(0).to(self.device)
        self.qnetwork_local.eval()
        with torch.no_grad():
            action_values = self.qnetwork_local(state)
        self.qnetwork_local.train()

        # Epsilon-greedy action selection
        if random.random() > eps:
            return np.argmax(action_values.cpu().data.numpy())
        else:
            return random.choice(np.arange(self.action_size))

    def learn(self, experiences, gamma):
        """Update value parameters using given batch of experience tuples.
        Params
        ======
            experiences (Tuple[torch.Tensor]): tuple of (s, a, r, s', done) tuples 
            gamma (float): discount factor
        """
        states, actions, rewards, next_states, dones = experiences

        # Get max predicted Q values (for next states) from target model
        Q_targets_next = self.qnetwork_target(next_states).detach().max(1)[0].unsqueeze(1)
        # Compute Q targets for current states 
        Q_targets = rewards + (gamma * Q_targets_next * (1 - dones))

        # Get expected Q values from local model
        Q_expected = self.qnetwork_local(states).gather(1, actions)

        # Compute loss
        loss = F.mse_loss(Q_expected, Q_targets)
        # Minimize the loss
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        # ------------------- update target network ------------------- #
        self.soft_update(self.qnetwork_local, self.qnetwork_target, self.tau)                     

    def soft_update(self, local_model, target_model, tau):
        """Soft update model parameters.
        θ_target = τ*θ_local + (1 - τ)*θ_target
        Params
        ======
            local_model (PyTorch model): weights will be copied from
            target_model (PyTorch model): weights will be copied to
            tau (float): interpolation parameter 
        """
        for target_param, local_param in zip(target_model.parameters(), local_model.parameters()):
            target_param.data.copy_(tau*local_param.data + (1.0-tau)*target_param.data)
            
    def train(self, env, n_episodes=2000, max_t=1000, eps_start=1.0, eps_end=0.01, eps_decay=0.995):
        """Train Agent by playing simulator

        Params
        ======
            n_episodes (int): maximum number of training episodes
            max_t (int): maximum number of timesteps per episode
            eps_start (float): starting value of epsilon, for epsilon-greedy action selection
            eps_end (float): minimum value of epsilon
            eps_decay (float): multiplicative factor (per episode) for decreasing epsilon
        """
        scores = []                        # list containing scores from each episode
        moving_avgs = []                   # list of moving averages
        scores_window = deque(maxlen=100)  # last 100 scores
        brain_name = env.brain_names[0]    # get env default branin name
        env_info = env.reset(train_mode=False)[brain_name] # intialize the environment
        eps = eps_start                    # initialize epsilon
        for i_episode in range(1, n_episodes+1):
            env_info = env.reset(train_mode=True)[brain_name]
            state = env_info.vector_observations[0]   # get the next state
            score = 0
            for t in range(max_t):
                action = self.act(state, eps).astype(int)
                env_info = env.step(action)[brain_name]
                next_state = env_info.vector_observations[0]   # get the next state
                reward = env_info.rewards[0]                   # get the reward
                done = env_info.local_done[0]                  # see if episode has finished
                self.step(state, action, reward, next_state, done)
                state = next_state
                score += reward
                if done:
                    break 
            scores_window.append(score)       # save most recent score
            scores.append(score)              # save most recent score
            moving_avg = np.mean(scores_window)  # calculate moving average
            moving_avgs.append(moving_avg)       # save most recent moving average
            eps = max(eps_end, eps_decay*eps) # decrease epsilon
            print('\rEpisode {}\tAverage Score: {:.2f}'.format(i_episode, np.mean(scores_window)), end="")
            if i_episode % 100 == 0:
                print('\rEpisode {}\tAverage Score: {:.2f}'.format(i_episode, moving_avg))
            if moving_avg>= 13.0:
                print('\nEnvironment solved in {:d} episodes!\tAverage Score: {:.2f}'.format(i_episode-100, moving_avg))
                self.save()
                break
        return scores, moving_avgs    

    def test(self, env, num_episodes = 10):
        brain_name = env.brain_names[0]
        scores = []                        # list of scores
        avg_scores = []                   # list of average scores
        for i_episode in range(1,num_episodes+1):
            env_info = env.reset(train_mode=False)[brain_name] # reset the environment
            state = env_info.vector_observations[0]            # get the current state
            score = 0                                          # initialize the score
            t = 1
            while True:
                action = self.act(state, eps=0)               # select an action
                env_info = env.step(action)[brain_name]        # send the action to the environment
                next_state = env_info.vector_observations[0]   # get the next state
                reward = env_info.rewards[0]                   # get the reward
                done = env_info.local_done[0]                  # see if episode has finished
                score += reward                                # update the score
                state = next_state                             # roll over the state to next time step
                # print('empisode: {}, step: {}, reward: {}, score: {}, scores: {}'.format(i_episode, t, reward, score, scores))
                t += 1
                if done:                                       # exit loop if episode finished
                    scores.append(score)
                    avg_scores.append(np.mean(scores))
                    print('\rEpisode {}\tAverage Score: {:.2f}'.format(i_episode, np.mean(scores)))
                    break    
        return scores, avg_scores 
    
    def save(self):
        """Save the model
        Params
        ======
            file: checkpoint file name
        """
        torch.save(self.qnetwork_local.state_dict(), self.checkpoint_file)

    def load(self):
        """Load the model
        Params
        ======
            file: checkpoint file name
        """
        self.qnetwork_local.load_state_dict(torch.load(self.checkpoint_file))