#!/usr/bin/env python3
import sys
try:
    sys.path.remove('/opt/ros/kinetic/lib/python2.7/dist-packages')
except Exception:
    pass

from envs import NaoEnv
from envs import NaoEnvPretrained

import numpy as np
import time
from datetime import datetime

from stable_baselines.common.policies import MlpPolicy as MlpLstmPolicy
from stable_baselines.ddpg.policies import MlpPolicy as DDPGMlpPolicy
from stable_baselines.common.vec_env import DummyVecEnv
from stable_baselines import PPO2
from stable_baselines.ddpg.noise import OrnsteinUhlenbeckActionNoise
from stable_baselines import DDPG
from stable_baselines.gail import generate_expert_traj
from stable_baselines.gail import ExpertDataset

ENV_ID = 'NaoEnv'
ENV_ID_PRETRAINED = 'NaoEnvPretrained'
PATH_MODEL = 'models/models_nao/'
PATH_PRETRAINED = 'pretrain/pretrain_nao/'
AGENT = "PPO2"
LOG_PATH = "logs/nao_env/"

def init_model(gui=True):
    env = globals()[ENV_ID](gui=gui)
    env = DummyVecEnv([lambda: env])
    if AGENT is "PPO2":
        model = PPO2(
                 MlpLstmPolicy,
                 env,
                 n_steps=4096,
                 verbose=2,
                 tensorboard_log= LOG_PATH + AGENT + "Agent/" +
                 datetime.now().strftime(
                     "%Y%m%d-%H%M%S"))
    if AGENT is "DDPG":
        action_noise = OrnsteinUhlenbeckActionNoise(
                    mean=np.zeros(env.action_space.shape[-1]),
                    sigma=float(0.5) * np.ones(env.action_space.shape[-1]))

        model = DDPG(
            DDPGMlpPolicy,
            env,
            verbose=2,
            param_noise=None,
            action_noise=action_noise,
            tensorboard_log="logs/" + AGENT + "Agent/" +
            datetime.now().strftime(
                "%Y%m%d-%H%M%S"))
    return env, model


def train(num_timesteps, seed, model_path=None):

    env, model = init_model()
    i = 0
    while i < num_timesteps:
        if i != 0:
            model.load(model_path + "/" + AGENT + "_" + repr(i))
        model.learn(total_timesteps=int(1e6))
        i += int(1e6)
        model.save(model_path + "/" + AGENT + "_" + repr(i))
    env.close()

def collect_pretrained_dataset(dataset_name):
    env = globals()[ENV_ID_PRETRAINED](gui=True)
    generate_expert_traj(env.walking_expert_speed,
                         PATH_PRETRAINED + dataset_name,
                         env, n_episodes=1)
    env.close()


def pretrained_model(dataset_name, model):
    dataset = ExpertDataset(expert_path=dataset_name + '.npz',
                            traj_limitation=1)
    model.pretrain(dataset, n_epochs=1000)
    return model


def pretrained_model_and_save(dataset_name):
    env, model = init_model(gui=False)
    model = pretrained_model(PATH_PRETRAINED + dataset_name, model)
    model.save(PATH_MODEL + AGENT + "_" + dataset_name)
    env.close()


def visualize(name_model):
    model = getattr(globals()[AGENT], 'load')(name_model)
    env = globals()[ENV_ID](gui=True)
    env = DummyVecEnv([lambda: env])
    # Enjoy trained agent
    obs = env.reset()
    while True:
        action, _states = model.predict(obs)
        obs, _, _, _ = env.step(action)
        env.render()
